"""Linear / Matmul 算子 — torch 实现 + C 调用约定 + math strategy，集中在一个文件。

算子:
    linear:  out = x @ weight + bias (fused)
    matmul:  out = x @ weight
"""

import logging

import numpy as np
import torch
from .. import register_op
from ...core.tensor import DSPTensor
from ...core.enums import Format
from ...core.convention import OpConvention
from ...core.block import pad_dim, get_block_shape

ZZ, NN = Format.ZZ, Format.NN

logger = logging.getLogger("dsp.ops")


# ============================================================
# C 调用约定
# ============================================================

def _pad_and_flatten(data: np.ndarray, dtype_name: str, fmt) -> np.ndarray:
    """pad 到 block 对齐 + row-major flatten。

    golden C 的索引:
      ZZ: a[row * K + col]  — 行优先 flat
      NN: b[col * K + row]  — 列优先 flat (同一个矩阵，不同存储顺序)
    """
    bh, bw = get_block_shape(dtype_name, fmt)
    h, w = data.shape[0], data.shape[1]
    ph, pw = pad_dim(h, bh), pad_dim(w, bw)

    if ph != h or pw != w:
        padded = np.zeros((ph, pw), dtype=data.dtype)
        padded[:h, :w] = data
    else:
        padded = data

    if str(fmt) == str(NN):
        # 列优先: flat[col * nrows + row]
        return padded.flatten(order='F').copy()
    return padded.flatten().copy()  # 行优先 (默认 C order)


def _prepare_2d(src0_2d, src1_2d, dtype_a, dtype_w):
    """单个 2D 矩阵对的准备：pad + flatten（ZZ/NN 行列优先）。

    异构权重: input 用 dtype_a 的 ZZ block，weight 用 dtype_w 的 NN block。
    同构时 dtype_a == dtype_w。

    Returns:
        (input_flat, weight_flat, M, K, N, orig_M, orig_N)
    """
    orig_M, K, orig_N = src0_2d.shape[0], src0_2d.shape[1], src1_2d.shape[1]

    input_flat = _pad_and_flatten(src0_2d, dtype_a, ZZ)   # 行优先，input dtype
    weight_flat = _pad_and_flatten(src1_2d, dtype_w, NN)  # 列优先，weight dtype

    bh, bw = get_block_shape(dtype_a, ZZ)
    M, K_padded = pad_dim(orig_M, bh), pad_dim(K, bw)
    _, bw_nn = get_block_shape(dtype_w, NN)
    N = pad_dim(orig_N, bw_nn)

    return input_flat, weight_flat, M, K_padded, N, orig_M, orig_N


def _to_2d_batches(arr):
    """任意维度 → (batch_shape, list[2D arrays])。1D 补成 2D。"""
    if arr.ndim < 2:
        return (), [arr.reshape(1, -1)]
    if arr.ndim == 2:
        return (), [arr]
    batch_shape = arr.shape[:-2]
    flat = arr.reshape(-1, arr.shape[-2], arr.shape[-1])
    return batch_shape, [flat[i] for i in range(flat.shape[0])]


class MatmulConvention(OpConvention, op="matmul"):
    """func(dst, input_zz, weight_nn, M, K, N)

    支持任意 batch 维度：按 batch 循环调 C 函数，结果 stack 回原 batch shape。
    """

    def output_shape(self, *inputs):
        return (*inputs[0].shape[:-1], inputs[1].shape[-1])

    def call_c_func(self, func, *inputs_np, **params):
        key = params.get("compute_key")
        dtype_a = str(key.src0) if key else "bf16"
        dtype_w = str(key.src1) if key and key.src1 else dtype_a

        batch_shape, src0_list = _to_2d_batches(inputs_np[0])
        _, src1_list = _to_2d_batches(inputs_np[1])
        # weight 可能没有 batch 维度，广播
        if len(src1_list) == 1 and len(src0_list) > 1:
            src1_list = src1_list * len(src0_list)

        results = []
        for s0, s1 in zip(src0_list, src1_list):
            input_flat, weight_flat, M, K, N, orig_M, orig_N = _prepare_2d(s0, s1, dtype_a, dtype_w)
            dst_flat = np.zeros(M * N, dtype=np.double)
            func(dst_flat, input_flat, weight_flat, M, K, N)
            results.append(dst_flat.reshape(M, N)[:orig_M, :orig_N].copy())

        if not batch_shape:
            return results[0]
        return np.stack(results).reshape(*batch_shape, *results[0].shape)


class LinearConvention(OpConvention, op="linear"):
    """func(dst, input_zz, weight_nn, bias, scale_exp, M, K, N)

    支持任意 batch 维度。bias 不参与 batch（广播到每个 batch）。
    """

    def output_shape(self, *inputs):
        return (*inputs[0].shape[:-1], inputs[1].shape[-1])

    def call_c_func(self, func, *inputs_np, **params):
        key = params.get("compute_key")
        dtype_a = str(key.src0) if key else "bf16"
        dtype_w = str(key.src1) if key and key.src1 else dtype_a
        scale_exp = params.get("scale_exp", 0)

        batch_shape, src0_list = _to_2d_batches(inputs_np[0])
        _, src1_list = _to_2d_batches(inputs_np[1])
        if len(src1_list) == 1 and len(src0_list) > 1:
            src1_list = src1_list * len(src0_list)

        if len(inputs_np) < 3 or inputs_np[2] is None:
            raise ValueError("linear 需要 bias 输入；无 bias 请用 matmul op")

        bias = inputs_np[2]
        results = []
        for s0, s1 in zip(src0_list, src1_list):
            input_flat, weight_flat, M, K, N, orig_M, orig_N = _prepare_2d(s0, s1, dtype_a, dtype_w)
            dst_flat = np.zeros(M * N, dtype=np.double)
            bias_pad = np.zeros(N, dtype=bias.dtype)
            bias_pad[:orig_N] = bias.flatten()[:orig_N]
            func(dst_flat, input_flat, weight_flat, bias_pad, scale_exp, M, K, N)
            results.append(dst_flat.reshape(M, N)[:orig_M, :orig_N].copy())

        if not batch_shape:
            return results[0]
        return np.stack(results).reshape(*batch_shape, *results[0].shape)


# ============================================================
# Math Strategy
# ============================================================

def _near_diagonal(m, n, scale=1.0, noise=0.01, seed=42):
    rng = torch.Generator().manual_seed(seed)
    base = torch.eye(m, n, dtype=torch.double) * scale
    perturbation = torch.randn(m, n, dtype=torch.double, generator=rng) * noise
    return base + perturbation


def _linear_math_strategy(inputs, source_map):
    # 内存全程 double，无需 dtype 适配
    x, weight, bias = inputs[0], inputs[1], inputs[2]
    from ...core.enums import TensorSource
    x_from_randn = source_map[0] == TensorSource.RANDN
    bias_from_randn = source_map[2] == TensorSource.RANDN

    dsp_dtype = x.dsp_dtype if isinstance(x, DSPTensor) else None
    M, K = x.shape[-2], x.shape[-1]
    N = weight.shape[-1]

    target = _near_diagonal(M, N, seed=42)
    if bias_from_randn:
        bias = torch.zeros(1, N, dtype=torch.double)

    if x_from_randn:
        new_x = _near_diagonal(M, K, seed=7)
        new_weight = torch.linalg.lstsq(new_x, target - bias).solution
        replacements = {
            0: _wrap(new_x, dsp_dtype),
            1: _wrap(new_weight, _get_dsp_dtype(inputs[1])),
        }
    else:
        x_s = x.double().reshape(-1, K)
        rhs = target - bias
        lam = 1e-4
        xtx = x_s.T @ x_s + lam * torch.eye(K, dtype=torch.double)
        new_weight = torch.linalg.solve(xtx, x_s.T @ rhs)
        replacements = {1: _wrap(new_weight, _get_dsp_dtype(inputs[1]))}

    if bias_from_randn:
        replacements[2] = _wrap(bias, _get_dsp_dtype(inputs[2]))

    return replacements, _wrap(target, dsp_dtype)


def _get_dsp_dtype(t):
    return t.dsp_dtype if isinstance(t, DSPTensor) else None


def _wrap(data, dsp_dtype):
    if dsp_dtype is not None:
        return DSPTensor.create(data, dsp_dtype)
    return data


# ============================================================
# 算子注册
# ============================================================

@register_op(
    weight=Format.NN,
    math_strategy=_linear_math_strategy,
)
def linear(x: torch.Tensor, weight: torch.Tensor, bias: torch.Tensor) -> torch.Tensor:
    """Linear: out = x @ weight + bias"""
    return torch.matmul(x, weight) + bias


@register_op(weight=Format.NN)
def matmul(x: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    """Matmul: out = x @ weight（无 bias 版本）"""
    return torch.matmul(x, weight)
