"""Re-quantization round-trip — 模拟 HW 在改变 block 布局时的重新量化。

用途:
    transpose 类 op：物理交换后，原始 bf16 subblock 边界不再匹配新的逻辑布局，
    HW 会按新布局重新压缩（block floating point），引入额外量化误差。我们在
    golden_c / pseudo_quant 路径里用 double 模拟这一步——通过一次
    "pad → blocked → double→bf16→double → from_blocked → unpad" round-trip
    把对应的量化误差烘进 double 值里。

注意:
    - 全程 double numpy，不走 torch
    - fmt 只支持 ZZ / NN（block 重排生效）；ND 不做 block 重排，等价于恒等
    - 1D / 0-D 跳过 block 重排（只做 codec round-trip）
"""

from __future__ import annotations

import numpy as np
import torch

from .block import pad_to_block, to_block, from_block
from .dtype import get_codec, get_dtype, DSPDtype
from .enums import Format


def requant_roundtrip(data: np.ndarray, dtype_name: str, fmt: Format) -> np.ndarray:
    """把 double ndarray 按 (dtype, fmt) 做一次量化/反量化 round-trip。

    Args:
        data: 任意形状的 double numpy array
        dtype_name: 目标 dtype 名（"bf16" / "bf8" / "double"）
        fmt: Format.ZZ / NN / ND

    Returns:
        同形状的 double numpy array，带上对应 (dtype, fmt) 的量化误差
    """
    if dtype_name == "double":
        return np.ascontiguousarray(data, dtype=np.double)

    dsp_dtype: DSPDtype = get_dtype(dtype_name)
    codec = get_codec(dsp_dtype)

    t = torch.from_numpy(np.ascontiguousarray(data, dtype=np.double))
    orig_shape = tuple(t.shape)

    if t.ndim >= 2 and fmt in (Format.ZZ, Format.NN):
        padded = pad_to_block(t, dtype_name, fmt)
        blocked = to_block(padded, dtype_name, fmt)
        # codec round-trip
        quantized = codec.from_double(blocked, dsp_dtype)
        back = codec.to_double(quantized, dsp_dtype)
        nd = from_block(back, dtype_name, fmt, tuple(padded.shape))
        nd = nd[..., :orig_shape[-2], :orig_shape[-1]].contiguous()
    else:
        # 1D / 0-D / ND 不做 block 重排，直接 codec round-trip
        quantized = codec.from_double(t, dsp_dtype)
        nd = codec.to_double(quantized, dsp_dtype)

    return nd.detach().cpu().numpy().astype(np.double)
