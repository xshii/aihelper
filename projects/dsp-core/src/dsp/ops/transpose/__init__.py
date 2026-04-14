"""Transpose 算子 — 交换最后两维，对标硬件 transpose 指令。

用法:
    dsp.ops.transpose(x)           # 默认交换最后两维
    dsp.ops.transpose(x, 0, 2)     # 交换 dim0 和 dim2

golden_c 路径: 走 C kernel dsp_transpose_<dut>（实际是 dsp_transpose_double），
按 batch 维循环，每次把一个 (R, C) 2D 切片展平成 flat double 喂给 C 做元素搬运。
是物理 transpose —— shape (R, C) → (C, R)，输出依然是 ZZ row-major，
不需要声明 output_fmts（output 默认 ZZ 由 infer_format 兜底）。

torch / pseudo_quant 路径: 走下面 register_op 注册的 torch 实现。
"""

from __future__ import annotations

import numpy as np
import torch

from .. import register_op
from ...core.convention import OpConvention


# ============================================================
# C 调用约定
# ============================================================

class TransposeConvention(OpConvention, op="transpose"):
    """transpose 的 golden_c 路径：按 batch 循环调 C，每次处理一个 (R, C) 2D 切片。"""

    def output_shape(self, *inputs: torch.Tensor) -> tuple[int, ...]:
        shape = inputs[0].shape
        if len(shape) < 2:
            return tuple(shape)
        return (*shape[:-2], shape[-1], shape[-2])

    def call_c_func(self, func, *inputs_np: np.ndarray, **params) -> np.ndarray:
        data = inputs_np[0]
        if data.ndim < 2:
            return data

        batch_shape = data.shape[:-2]
        R, C = data.shape[-2], data.shape[-1]
        n = R * C

        batched = data.reshape(-1, R, C) if batch_shape else data.reshape(1, R, C)
        results = []
        for i in range(batched.shape[0]):
            src_flat = np.ascontiguousarray(batched[i].flatten(), dtype=np.double)
            dst_flat = np.zeros(n, dtype=np.double)
            func(dst_flat, src_flat, R, C)
            results.append(dst_flat.reshape(C, R).copy())

        stacked = np.stack(results)
        if batch_shape:
            return stacked.reshape(*batch_shape, C, R)
        return stacked[0]


# ============================================================
# 算子注册
# ============================================================

@register_op
def transpose(x: torch.Tensor, dim0: int = -2, dim1: int = -1) -> torch.Tensor:
    """交换指定的两个维度。默认交换最后两维。

    Args:
        x: 输入 tensor
        dim0: 第一个维度（默认 -2）
        dim1: 第二个维度（默认 -1）
    """
    if x.ndim < 2:
        return x
    return x.transpose(dim0, dim1).contiguous()
