"""LayerNorm1D 算子 — 按最后一维 normalize，torch 实现 + C 调用约定。

算子: out[..., c] = gamma[c] * (x[..., c] - mean[...]) / sqrt(var[...] + eps) + beta[c]

mean/var 在最后一维（cols）上求；gamma/beta shape = (cols,)，跨其它维度广播。

C 接口: (dst, input, gamma, beta, batch, matrix, rows, cols)
    Convention 对任意维度 x 一次性调 kernel：`x.padded_shape[:-2]` 前置维 collapse
    成 `batch`，`matrix=1`，`rows = pad(M, bh_zz)`，`cols = pad(D, bw_zz)`。

Format 声明:
    x / gamma / beta 全是 Format.ZZ
    - x (B, M, D) → 保留 B，pad 末 2 维到 `(bh_zz, bw_zz)`，行优先 flatten
    - gamma / beta 1D (D,) → 走 _pad_1d 到 `bw_zz`
    （统一由 core/prepare_args.py 的规则处理）

已知的 QSNR WARN:
    ZZ 规则把 cols pad 到 `bw_zz`（BF16 下 = 16），但 C kernel 内部按 `subblock_size`
    （BF16 下 = 8）算 stride，两者在 `D not multiple of bw_zz` 时不一致，导致 kernel
    读 buffer 时 stride 对不上。现象是 layernorm 的 pseudo_quant vs golden_c QSNR
    显著下降。要彻底修需要 C kernel 加显式 `cols_mem` 参数；这里作为已知 WARN 保留。
"""

import numpy as np
import torch

from .. import register_op
from ...core.enums import Format
from ...core.convention import OpConvention


class LayerNorm1dConvention(OpConvention, op="layernorm1d"):
    """一次把整块 `(B, M_pad, D_pad)` 喂给 C kernel。"""

    def output_shape(self, *inputs, **op_params):
        return tuple(inputs[0].shape)

    def call_c_func(self, func, x, gamma, beta, **_):
        # x.padded_shape 拆 batch / rows / cols
        #   ≥2D: (*outer, rows_pad, cols_pad)，outer collapse 成 batch
        #   1D : (cols_pad,)，看作 rows=1 的单行
        if len(x.padded_shape) >= 2:
            *outer, rows_pad, cols_pad = x.padded_shape
        elif len(x.padded_shape) == 1:
            outer, rows_pad, cols_pad = [], 1, x.padded_shape[0]
        else:
            raise ValueError(f"layernorm1d: 不支持 0-D x, padded_shape={x.padded_shape}")

        batch_total = int(np.prod(outer)) if outer else 1

        # gamma / beta 末维校验（应等于 x 的 orig cols）
        orig_cols = x.orig_shape[-1] if x.orig_shape else 0
        if gamma.orig_shape[-1] != orig_cols or beta.orig_shape[-1] != orig_cols:
            raise ValueError(
                f"layernorm1d: gamma/beta 末维长度应等于 x.orig_cols={orig_cols}, "
                f"实际 gamma={gamma.orig_shape}, beta={beta.orig_shape}"
            )

        # C kernel 契约：cols 既是 reduction count 又是 stride 推算基础
        # （kernel 内部 cols_mem = pad(cols, subblock)）
        # Python 侧 buffer 已按 ZZ 的 bw_zz pad，这里直接把 padded cols 传给 kernel
        dst = np.zeros(batch_total * rows_pad * cols_pad, dtype=np.double)
        func(dst, x.flat, gamma.flat, beta.flat,
             batch_total, 1, rows_pad, cols_pad)

        if outer:
            return dst.reshape(*outer, rows_pad, cols_pad)
        if rows_pad == 1:
            return dst.reshape(cols_pad)
        return dst.reshape(rows_pad, cols_pad)


@register_op(x=Format.ZZ, gamma=Format.ZZ, beta=Format.ZZ)
def layernorm1d(x: torch.Tensor, gamma: torch.Tensor, beta: torch.Tensor) -> torch.Tensor:
    """LayerNorm1D: 按最后一维做 normalize。

    - x: shape (..., cols)
    - gamma, beta: shape (cols,)，跨前面维度广播
    """
    mean = x.mean(dim=-1, keepdim=True)
    var = x.var(dim=-1, keepdim=True, unbiased=False)
    return gamma * (x - mean) / torch.sqrt(var + 1e-5) + beta
