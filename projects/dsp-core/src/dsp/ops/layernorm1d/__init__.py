"""LayerNorm1D 算子 — 按最后一维 normalize，torch 实现 + C 调用约定。

算子: out[..., c] = gamma[c] * (x[..., c] - mean[...]) / sqrt(var[...] + eps) + beta[c]

mean/var 在最后一维（cols）上求；gamma/beta shape = (cols,)，跨其它维度广播。

C 接口: (dst, input, gamma, beta, batch, matrix, rows, cols)
    - input / dst 形状 = (batch, matrix, rows, cols_mem), cols_mem = pad_dim(cols, subblock)
    - gamma / beta 形状 = (cols_mem,)
    - 每个 (b, m, r) 行在前 cols 个元素上求 mean/var
    - 总 subblock 数 = batch * matrix * rows * cols_mem / subblock

config.hw.golden_c_count_mode 控制 caller 往 cols 参数里传什么：
    "orig":   cols = 原始 feature 维长度（可非对齐），reduction 只走原始元素
    "padded": cols = pad_dim(原始长度, subblock)，reduction 走整个 padded 区（含 0）
"""

import numpy as np
import torch

from .. import register_op
from ...core.convention import OpConvention
from ...core.block import pad_dim


# ============================================================
# C 调用约定
# ============================================================

class LayerNorm1dConvention(OpConvention, op="layernorm1d"):
    """把任意 shape 的 input 看成 (batch=1, matrix=1, rows=prod(shape[:-1]), cols=shape[-1])。

    gamma/beta: 要求 shape == (cols,)（跨外层广播），或 flat 后长度与 input 相同（视为逐元素）。
    我们只支持前者（标准 LN 约定）。
    """

    def output_shape(self, *inputs):
        return tuple(inputs[0].shape)

    def call_c_func(self, func, *inputs_np, **params):
        from ...config import config as cfg

        x = inputs_np[0]
        gamma = inputs_np[1]
        beta = inputs_np[2]
        orig_shape = x.shape
        orig_cols = orig_shape[-1]
        rows = int(np.prod(orig_shape[:-1])) if x.ndim >= 2 else 1
        batch = 1
        matrix = 1

        key = params.get("compute_key")
        from ...core.dtype import get_dtype
        dtype_name = str(key.src0) if key else "bf16"
        sub = get_dtype(dtype_name).subblock_size
        cols_mem = pad_dim(orig_cols, sub)

        # 按 golden_c_count_mode 决定传给 C 的 cols 值
        mode = cfg.hw.golden_c_count_mode
        if mode == "orig":
            c_cols = orig_cols
        elif mode == "padded":
            c_cols = cols_mem
        else:
            raise ValueError(f"未知 golden_c_count_mode: {mode}")

        # 把 input pad 到 (rows, cols_mem) 再 flat
        x_2d = x.reshape(rows, orig_cols).astype(np.double)
        if cols_mem != orig_cols:
            x_padded = np.zeros((rows, cols_mem), dtype=np.double)
            x_padded[:, :orig_cols] = x_2d
        else:
            x_padded = x_2d
        input_flat = x_padded.reshape(-1).copy()

        # gamma / beta: shape (cols,) → pad 到 cols_mem
        gamma_flat = gamma.flatten().astype(np.double)
        beta_flat = beta.flatten().astype(np.double)
        if gamma_flat.size != orig_cols or beta_flat.size != orig_cols:
            raise ValueError(
                f"layernorm1d: gamma/beta 形状应是 (cols={orig_cols},), "
                f"实际 gamma={gamma_flat.shape}, beta={beta_flat.shape}"
            )
        if cols_mem != orig_cols:
            gamma_pad = np.zeros(cols_mem, dtype=np.double)
            beta_pad = np.zeros(cols_mem, dtype=np.double)
            gamma_pad[:orig_cols] = gamma_flat
            beta_pad[:orig_cols] = beta_flat
        else:
            gamma_pad = gamma_flat
            beta_pad = beta_flat

        total_mem = batch * matrix * rows * cols_mem
        dst_flat = np.zeros(total_mem, dtype=np.double)
        func(dst_flat, input_flat, gamma_pad, beta_pad, batch, matrix, rows, c_cols)

        # 从 padded 2D 中取前 orig_cols 列，reshape 回原 shape
        dst_2d = dst_flat.reshape(rows, cols_mem)[:, :orig_cols]
        return dst_2d.reshape(orig_shape).copy()


# ============================================================
# 算子注册
# ============================================================

@register_op
def layernorm1d(x: torch.Tensor, gamma: torch.Tensor, beta: torch.Tensor) -> torch.Tensor:
    """LayerNorm1D: 按最后一维做 normalize。

    - x: shape (..., cols)
    - gamma, beta: shape (cols,)，跨前面维度广播
    """
    mean = x.mean(dim=-1, keepdim=True)
    var = x.var(dim=-1, keepdim=True, unbiased=False)
    return gamma * (x - mean) / torch.sqrt(var + 1e-5) + beta
