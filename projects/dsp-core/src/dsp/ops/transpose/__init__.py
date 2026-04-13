"""Transpose 算子 — 支持指定交换维度，支持 block 重排。

用法:
    dsp.ops.transpose(x)           # 默认交换最后两维
    dsp.ops.transpose(x, 0, 2)     # 交换 dim0 和 dim2

流程 (golden_c 模式):
    blocked DUT → unblock(去 padding) → 转置 → re-pad(新 shape) → re-block
"""

from __future__ import annotations

import numpy as np
import torch

from .. import register_op
from ...core.enums import Format
from ...core.convention import OpConvention
from ...core.block import pad_dim, get_block_shape, to_block, from_block


# ============================================================
# C 调用约定
# ============================================================

class TransposeConvention(OpConvention, op="transpose"):
    """transpose 不调 C 函数，纯 Python 做 unblock → transpose → re-block。"""

    def output_shape(self, *inputs: torch.Tensor) -> tuple[int, ...]:
        shape = inputs[0].shape
        if len(shape) < 2:
            return tuple(shape)
        return (*shape[:-2], shape[-1], shape[-2])

    def call_c_func(self, func, *inputs_np: np.ndarray, **params) -> np.ndarray:
        data = inputs_np[0]
        dtype_name = params.get("dtype_name", "bf16")
        fmt = params.get("fmt", "zz")
        orig_shape = params.get("orig_shape", data.shape)

        if len(orig_shape) >= 2:
            h, w = orig_shape[-2], orig_shape[-1]
            bh, bw = get_block_shape(dtype_name, fmt)
            ph, pw = pad_dim(h, bh), pad_dim(w, bw)

            t = torch.from_numpy(data.reshape(-1))
            nd = from_block(t.reshape(ph * pw // (bh * bw), bh, bw),
                           dtype_name, fmt, (ph, pw))
            nd_np = nd.numpy()[:h, :w]
        else:
            nd_np = data

        transposed = nd_np.T.copy()

        new_h, new_w = transposed.shape[-2], transposed.shape[-1]
        ph_new, pw_new = pad_dim(new_h, get_block_shape(dtype_name, fmt)[0]), \
                         pad_dim(new_w, get_block_shape(dtype_name, fmt)[1])

        padded = np.zeros((ph_new, pw_new), dtype=transposed.dtype)
        padded[:new_h, :new_w] = transposed

        t_out = to_block(torch.from_numpy(padded), dtype_name, fmt)
        return t_out.numpy().reshape(-1).copy()


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
