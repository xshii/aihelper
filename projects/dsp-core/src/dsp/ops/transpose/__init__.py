"""Transpose 算子 — 交换指定两维，对标硬件 transpose 指令。

API 对齐 torch.transpose(input, dim0, dim1): dim0/dim1 **必填**，无默认值。
想要"最后两维"的便捷用法请显式写 transpose(x, -2, -1)。

返回值语义对齐 torch: torch / pseudo_quant 路径返回 **non-contiguous view**
（零拷贝、共享 storage、stride 重排），和 torch.transpose 原生行为一致。
不在 op 函数里强制 .contiguous()，写 DUT 文件时由 _save_tensor 在边界处
统一 .contiguous()，保护 to_block 的 row-major 假设。

用法:
    dsp.ops.transpose(x, -2, -1)   # 显式最后两维
    dsp.ops.transpose(x, 0, 2)     # 交换 dim0 和 dim2

golden_c 路径: 物理 transpose，直接在 double numpy 上 np.swapaxes(dim0, dim1)。
Python 层收到的 numpy 已是逻辑 shape（无 padding），padding 由
save_op_output → _save_tensor → to_block 在写 DUT 文件时按输出 dtype
的 tile 自动施加。dispatch_golden_c 内部 .copy() 已经把 swapaxes 的
non-contiguous view 拷成 C-contiguous，call_c_func 不需要再 ascontiguousarray。

dim0/dim1 通过 ops/__init__.py wrapper 收集非 tensor 位置参数构成 op_params，
经 dispatch.dispatch_golden_c → call.compute → conv.call_c_func 透传进来，
支持任意维度对调。

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

    def output_shape(self, *inputs: torch.Tensor, dim0: int,
                     dim1: int) -> tuple[int, ...]:
        shape = list(inputs[0].shape)
        shape[dim0], shape[dim1] = shape[dim1], shape[dim0]
        return tuple(shape)

    def call_c_func(self, func, *inputs_np: np.ndarray, **params) -> np.ndarray:
        data = inputs_np[0]
        dim0 = params["dim0"]
        dim1 = params["dim1"]
        # 返回 non-contiguous view，由 dispatch_golden_c 的 .copy() 拷成 C-contiguous
        return np.swapaxes(data, dim0, dim1)


# ============================================================
# 算子注册
# ============================================================

@register_op
def transpose(x: torch.Tensor, dim0: int, dim1: int) -> torch.Tensor:
    """交换指定的两个维度。对齐 torch.transpose: dim0/dim1 必填，返回 non-contiguous view。

    Args:
        x: 输入 tensor
        dim0: 第一个维度
        dim1: 第二个维度
    """
    return x.transpose(dim0, dim1)
