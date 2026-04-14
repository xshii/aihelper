"""Transpose 算子 — 交换最后两维，对标硬件 transpose 指令。

用法:
    dsp.ops.transpose(x)           # 默认交换最后两维
    dsp.ops.transpose(x, 0, 2)     # 交换 dim0 和 dim2（仅 torch / pseudo_quant 路径）

golden_c 路径: 物理 transpose，直接在 double numpy 上 swapaxes(-2, -1)。
Python 层收到的 numpy 已是逻辑 shape（无 padding），padding 由
save_op_output → _save_tensor → to_block 在写 DUT 文件时按输出 dtype
的 tile 自动施加，call_c_func 层不需要处理。

已知限制: dispatch 链路目前不透传 dim0/dim1 kwargs 到 call_c_func，
所以 GOLDEN_C 模式下 transpose 始终是"最后两维"语义。若需要任意
dim 对调（例如 4D 下交换 dim1/dim2），目前只能走 torch / pseudo_quant 路径。

torch / pseudo_quant 路径: 走下面 register_op 注册的 torch 实现。
C kernel dsp_transpose_double 仍保留在 dsp_transpose.h 作为 header-only
辅助，供其他 op 的 kernel 内部"先 transpose 再计算"时复用。
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
    """transpose 的 golden_c 路径：直接 numpy swapaxes，不调 C kernel。"""

    def output_shape(self, *inputs: torch.Tensor) -> tuple[int, ...]:
        shape = inputs[0].shape
        if len(shape) < 2:
            return tuple(shape)
        return (*shape[:-2], shape[-1], shape[-2])

    def call_c_func(self, func, *inputs_np: np.ndarray, **params) -> np.ndarray:
        data = inputs_np[0]
        if data.ndim < 2:
            return data
        return np.ascontiguousarray(np.swapaxes(data, -2, -1))


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
