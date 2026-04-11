"""算子调用约定：每种 op 声明自己的 C 函数调用方式。

完整的输入输出流程:
    输入: float → padding → 分型(ZZ/NN) → [传给 binding 做 to_dut] → C 函数
    输出(比数): [binding 做 acc→float] → 去分型 → 去padding → 比数
    输出(验证): [binding 做 acc→dut] → 不动（已是 blocked DUT 格式）
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np
import torch


# ============================================================
# 注册表
# ============================================================

_CONVENTIONS: dict[str, OpConvention] = {}


def get_convention(op_name: str) -> Optional[OpConvention]:
    return _CONVENTIONS.get(op_name)


def require_convention(op_name: str) -> OpConvention:
    """查 OpConvention，找不到直接 raise 并给出诊断信息。"""
    conv = _CONVENTIONS.get(op_name)
    if conv is not None:
        return conv
    existing = list(_CONVENTIONS.keys())
    from ..core.errors import ConventionNotFound
    raise ConventionNotFound(
        f"算子 '{op_name}' 无 OpConvention。\n"
        f"已注册的 convention: {existing}\n"
        f"修复: 在 op_convention.py 添加 class MyConvention(OpConvention, op=\"{op_name}\"): ...\n"
        f"或复用已有的（在已有 Convention 的 op= 列表中加 \"{op_name}\"）。"
    )


# ============================================================
# 分型辅助
# ============================================================

def _pad_dim(dim: int, block: int) -> int:
    return dim + (block - dim % block) % block


def _pad_2d(data: np.ndarray, bh: int, bw: int) -> np.ndarray:
    """pad float 2D array 到 block 对齐。"""
    h, w = data.shape[-2], data.shape[-1]
    ph, pw = _pad_dim(h, bh), _pad_dim(w, bw)
    if ph == h and pw == w:
        return data
    padded = np.zeros((*data.shape[:-2], ph, pw), dtype=data.dtype)
    padded[..., :h, :w] = data
    return padded


def _to_blocked(data: np.ndarray, bh: int, bw: int) -> np.ndarray:
    """padded 2D → block 重排（ZZ/NN 共享逻辑）。返回 flat。"""
    h, w = data.shape[-2], data.shape[-1]
    blocked = data.reshape(h // bh, bh, w // bw, bw)
    blocked = blocked.transpose(0, 2, 1, 3)  # [n_bh, n_bw, bh, bw]
    return blocked.reshape(-1).copy()


def _from_blocked(flat: np.ndarray, bh: int, bw: int, padded_h: int, padded_w: int) -> np.ndarray:
    """flat → 反 block 重排 → padded 2D。"""
    n_bh, n_bw = padded_h // bh, padded_w // bw
    blocked = flat.reshape(n_bh, n_bw, bh, bw)
    blocked = blocked.transpose(0, 2, 1, 3)  # [n_bh, bh, n_bw, bw]
    return blocked.reshape(padded_h, padded_w)


def _unpad_2d(data: np.ndarray, orig_h: int, orig_w: int) -> np.ndarray:
    return data[..., :orig_h, :orig_w].copy()


def _get_block_shape(dtype_name: str, fmt: str) -> tuple:
    from ..golden.manifest import get_block_shape
    return get_block_shape(dtype_name, fmt)


# ============================================================
# 基类
# ============================================================

class OpConvention:
    def __init_subclass__(cls, op: str | list[str] = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if op is not None:
            ops = [op] if isinstance(op, str) else op
            instance = cls()
            for o in ops:
                _CONVENTIONS[o] = instance

    def output_shape(self, *inputs: torch.Tensor) -> tuple:
        return inputs[0].shape

    def call_c_func(self, func: Callable, *inputs_np: np.ndarray, **params) -> np.ndarray:
        raise NotImplementedError


# ============================================================
# 内置 Convention
# ============================================================

class UnaryConvention(OpConvention, op="abs"):
    """func(dst, src0, count) — ND，不分块"""

    def call_c_func(self, func, *inputs_np, **params):
        src0 = inputs_np[0].flatten()
        dst = np.zeros_like(src0)
        func(dst, src0, src0.size)
        return dst


class ElementwiseConvention(OpConvention, op=["add", "mul", "sub"]):
    """func(dst, src0, src1, count) — ND，不分块"""

    def call_c_func(self, func, *inputs_np, **params):
        src0 = inputs_np[0].flatten()
        src1 = inputs_np[1].flatten()
        count = min(src0.size, src1.size)
        dst = np.zeros(count, dtype=np.float32)
        func(dst, src0[:count], src1[:count], count)
        return dst


class MatmulConvention(OpConvention, op="matmul"):
    """func(dst_zz, input_zz, weight_nn, M, K, N)

    流程:
      float input[M,K] → pad → ZZ block → flatten → [binding: to_dut → C → acc_to_float] → unblock → unpad
      float weight[K,N] → pad → NN block → flatten
    """

    def output_shape(self, *inputs):
        return (*inputs[0].shape[:-1], inputs[1].shape[-1])

    def call_c_func(self, func, *inputs_np, **params):
        src0, src1 = inputs_np[0], inputs_np[1]
        if src0.ndim < 2: src0 = src0.reshape(1, -1)
        if src1.ndim < 2: src1 = src1.reshape(-1, 1)

        orig_M, K, orig_N = src0.shape[-2], src0.shape[-1], src1.shape[-1]
        key = params.get("compute_key")
        dtype_name = str(key.src0) if key else "int16"
        bh, bw = _get_block_shape(dtype_name, "zz")

        # float → pad → 分型(block) → flatten
        src0_blocked = _to_blocked(_pad_2d(src0, bh, bw), bh, bw)
        src1_blocked = _to_blocked(_pad_2d(src1, bh, bw), bh, bw)

        M = _pad_dim(orig_M, bh)
        K_padded = _pad_dim(K, bw)
        N = _pad_dim(orig_N, bw)
        dst_flat = np.zeros(M * N, dtype=np.float32)

        # → [binding 做 to_dut → C 函数 → acc_to_float]
        func(dst_flat, src0_blocked, src1_blocked, M, K_padded, N)

        # acc_to_float 结果 → 去分型 → 去 padding
        dst_2d = _from_blocked(dst_flat, bh, bw, M, N)
        return _unpad_2d(dst_2d, orig_M, orig_N)


class LinearConvention(OpConvention, op="linear"):
    """func(dst_zz, input_zz, weight_nn, bias_nd, scale_exp, M, K, N)

    流程同 MatmulConvention，bias 不分块只 pad。
    """

    def output_shape(self, *inputs):
        return (*inputs[0].shape[:-1], inputs[1].shape[-1])

    def call_c_func(self, func, *inputs_np, **params):
        src0, src1 = inputs_np[0], inputs_np[1]
        src2 = inputs_np[2] if len(inputs_np) > 2 else None
        scale_exp = params.get("scale_exp", 0)

        if src0.ndim < 2: src0 = src0.reshape(1, -1)
        if src1.ndim < 2: src1 = src1.reshape(-1, 1)

        orig_M, K, orig_N = src0.shape[-2], src0.shape[-1], src1.shape[-1]
        key = params.get("compute_key")
        dtype_name = str(key.src0) if key else "int16"
        bh, bw = _get_block_shape(dtype_name, "zz")

        # float → pad → 分型 → flatten
        src0_blocked = _to_blocked(_pad_2d(src0, bh, bw), bh, bw)
        src1_blocked = _to_blocked(_pad_2d(src1, bh, bw), bh, bw)

        M = _pad_dim(orig_M, bh)
        K_padded = _pad_dim(K, bw)
        N = _pad_dim(orig_N, bw)
        dst_flat = np.zeros(M * N, dtype=np.float32)

        if src2 is not None:
            # bias: ND，只 pad 不分型
            bias_pad = np.zeros(N, dtype=src2.dtype)
            bias_pad[:orig_N] = src2.flatten()[:orig_N]
            func(dst_flat, src0_blocked, src1_blocked, bias_pad, scale_exp, M, K_padded, N)
        else:
            func(dst_flat, src0_blocked, src1_blocked, scale_exp, M, K_padded, N)

        # → 去分型 → 去 padding
        dst_2d = _from_blocked(dst_flat, bh, bw, M, N)
        return _unpad_2d(dst_2d, orig_M, orig_N)


class CorrelateConvention(OpConvention, op="correlate"):
    """func(dst, signal_nd, template_nd, signal_len) — ND，不分块"""

    def output_shape(self, *inputs):
        n = inputs[0].shape[-1] + inputs[1].shape[-1] - 1
        return (*inputs[0].shape[:-1], n)

    def call_c_func(self, func, *inputs_np, **params):
        src0, src1 = inputs_np[0], inputs_np[1]
        n_out = src0.shape[-1] + src1.shape[-1] - 1
        dst = np.zeros(n_out, dtype=np.float32)
        func(dst, src0.flatten(), src1.flatten(), src0.shape[-1])
        return dst
