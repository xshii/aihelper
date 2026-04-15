"""Transpose 算子 — 交换指定两维，对标硬件 transpose 指令。

API 对齐 torch.transpose(input, dim0, dim1): dim0/dim1 **必填**，无默认值。

golden_c 特殊处理:
    transpose 不走框架的 Format 预处理（`raw=True` opt-out），因为：
    1. 框架的 pad 规则依赖输入 shape 的"最后 2 维是 matrix"这个假设；transpose 的
       意义就是改变最后 2 维，pad 必须在 swap 之后按新 shape 重做
    2. HW 物理 transpose 会重排 block floating point 的 subblock 边界，必须按新
       布局 re-quant。这一步用 `core/requant.py` 的 codec round-trip 在 double 上
       模拟，把 HW 的量化误差烘进值里

流程:
    1. 收到原始 double ndarray
    2. np.swapaxes → 新 shape 的 un-pad double
    3. requant_roundtrip(..., Format.ZZ) 按 ZZ 新布局 re-quant → 引入 HW 量化误差
    4. 返回 un-pad double，框架按 orig output shape crop（no-op since no pad）

用法:
    dsp.ops.transpose(x, -2, -1)   # 显式最后两维
    dsp.ops.transpose(x, 0, 2)     # 交换 dim0 和 dim2
"""

from __future__ import annotations

import numpy as np
import torch

from .. import register_op
from ...core.convention import OpConvention
from ...core.enums import Format
from ...core.requant import requant_roundtrip


class TransposeConvention(OpConvention, op="transpose"):
    """raw=True 模式：call_c_func 收到 raw double ndarray，自己处理 pad / re-quant。"""

    def output_shape(self, *inputs, dim0: int, dim1: int) -> tuple[int, ...]:
        shape = list(inputs[0].shape)
        shape[dim0], shape[dim1] = shape[dim1], shape[dim0]
        return tuple(shape)

    def call_c_func(self, func, *inputs_np: np.ndarray, **params) -> np.ndarray:
        data = inputs_np[0]
        dim0 = params["dim0"]
        dim1 = params["dim1"]
        key = params.get("compute_key")
        dtype_name = str(key.src0) if key and key.src0 else "bf16"

        # 物理 swap
        swapped = np.ascontiguousarray(np.swapaxes(data, dim0, dim1))
        # HW 会按新布局 re-quant; 在 double 上用 codec round-trip 模拟
        return requant_roundtrip(swapped, dtype_name, Format.ZZ)


@register_op(raw=True)
def transpose(x: torch.Tensor, dim0: int, dim1: int) -> torch.Tensor:
    """交换指定的两个维度。对齐 torch.transpose: dim0/dim1 必填。

    Args:
        x: 输入 tensor
        dim0: 第一个维度
        dim1: 第二个维度
    """
    return x.transpose(dim0, dim1)
