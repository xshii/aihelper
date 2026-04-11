"""分型转换 — 组合 layout（block 重排）+ golden C convert（类型转换）。

分型之间不能直接转，必须经过 float32 中转:
    ZZ(DUT) → float32 → NN(DUT)

流程:
    1. DUT blocked → unblock 回 ND
    2. ND(DUT) → dsp_convert → ND(float32)
    3. ND(float32) → dsp_convert → ND(DUT)
    4. ND(DUT) → reblock 到目标分型

用法:
    from dsp.golden.format_convert import convert_format
    result = convert_format(data, src_fmt="zz", dst_fmt="nn",
                            dtype_name="int16")
"""

from __future__ import annotations

import numpy as np
import torch

from ..core.enums import Format
from ..data.layout import _to_block, _from_block
from ..golden.manifest import get_block_shape
from .call import convert


def convert_format(data: torch.Tensor, src_fmt: str, dst_fmt: str,
                   dtype_name: str) -> torch.Tensor:
    """分型转换: src_fmt(DUT) → ACC → dst_fmt(DUT)。

    Args:
        data: blocked tensor（src_fmt 格式）
        src_fmt: 源分型（"zz" / "nn" / "nd"）
        dst_fmt: 目标分型
        dtype_name: DUT 类型名（如 "int16"）

    Returns:
        blocked tensor（dst_fmt 格式）
    """
    src_fmt = Format(src_fmt)
    dst_fmt = Format(dst_fmt)

    if src_fmt == dst_fmt:
        return data

    orig_shape = data.shape
    src_block = get_block_shape(dtype_name, src_fmt)
    dst_block = get_block_shape(dtype_name, dst_fmt)

    # 1. unblock 回 ND
    if src_fmt != Format.ND:
        nd_data = _from_block(data, src_fmt, src_block, orig_shape)
    else:
        nd_data = data

    # 2. DUT → ACC（通过 golden C convert）
    flat = nd_data.detach().cpu().float().numpy().flatten().astype(np.float32)
    acc_flat = convert(flat, dtype_name, "float32")  # DUT → float（ACC 中转）

    # 3. ACC → DUT（目标类型，可能相同）
    dut_flat = convert(acc_flat, "float32", dtype_name)

    # 4. reshape 回 ND shape
    nd_result = torch.from_numpy(dut_flat.copy()).reshape(nd_data.shape)

    # 5. reblock 到目标分型
    if dst_fmt != Format.ND:
        return _to_block(nd_result, dst_fmt, dst_block)
    return nd_result
