"""Golden-C 输入预处理 — @register_op 声明的 Format → flat double ndarray。

动机:
    linear / matmul / layernorm1d 的 call_c_func 里曾经各自重复写
      "pad 到 block + flatten + batch 管理 + output crop"
    逻辑。"pad 到 block + flatten" 部分完全由 Format + dtype 决定，属于确定性流程。
    本模块把它抽成纯函数，调用方只负责"组装 C 调用签名 + 调 func（或 for 循环调 B
    次）"。

设计契约:
    - 框架只管 pad + flatten，产生单个 PreparedArg（N-D tensor 保留 batch 维，不切片）
    - Convention.call_c_func 拿到整块 PreparedArg，自己决定如何喂 C kernel：
        * matmul / linear: for 循环逐 2D 片调 kernel（kernel 只认单片 (M,K,N)）
        * layernorm1d: 一次把 (B, M_pad, D_pad) 整块喂给 kernel
          （kernel 原生支持 batch/matrix 维度）
    - 这样框架不需要任何 "batch_2d" flag，op 完全掌控计算语义

三条 Format 规则（见 core/block.py 的 BlockShape）:
    ZZ (row-major 2D block):
        1D    → pad 长度到 `bw_zz`，直接 flatten
        2D    → pad (h, w) 到 (bh_zz, bw_zz)，行优先 flatten
        ≥3D   → 保留 batch 维度，last-2-dim 按 2D ZZ 规则 pad，C-order flatten
                padded_shape = (*batch, pad(h, bh_zz), pad(w, bw_zz))

    NN (col-major 2D block):
        1D    → pad 长度到 `bw_nn`，直接 flatten
        2D    → pad (h, w) 到 (bh_nn, bw_nn)，列优先 flatten
        ≥3D   → 保留 batch 维度，last-2-dim 按 2D NN 规则 pad
                padded_shape = (*batch, pad(h, bh_nn), pad(w, bw_nn))
                每个 batch 片内部是列优先 flatten（batch 维仍是 C-order）

    ND (natural dim):
        任意维 → 末维 pad 到 `bh_zz`（= bw_nn 不变式），前面维度原样，C-order flatten
        典型用途：1D 向量（如 linear.bias）——长度 pad 到 bh_zz，由不变式自动对齐
        NN 矩阵的 col 轴；或 elementwise-over-last-dim 类 op 的 gamma/beta

关键不变式（core/block.py 的 BLOCK_TYPES 保证 BF8/BF16/DOUBLE 全满足）:
    bh_zz == bw_nn          ⟹ 2D 矩阵 M_block == N_block
    bw_zz == bh_nn          ⟹ 2D 矩阵 K_block 在左右算子一致
    ND 末维 pad 到 bh_zz    ⟹ 因为 bh_zz == bw_nn，linear bias 作为 ND 1D 向量
                              自动对齐 weight 的 col 轴 pad 后的 N（bw_nn），无需
                              跨 arg 手工对齐

未声明 fmt 的 op（如 transpose）通过 @register_op(raw=True) 走 raw 透传，不进本模块。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .enums import Format
from .block import get_block_shape, pad_dim


@dataclass
class PreparedArg:
    """单个 tensor arg 预处理后的表示。

    Fields:
        flat: pad 后的 C-contiguous double 1D ndarray
        orig_shape: 预处理前的 shape（完整 N-D）
        padded_shape: pad 后的 shape（batch 维不变，末 2 维 / 末 1 维按规则 pad）
        fmt: 声明的 Format

    call_c_func 通常只读 padded_shape（用于算 M/K/N/rows/cols 之类）和 flat（喂 C）。
    orig_shape 留给可能需要对比 pre/post pad 的 op 用。
    """

    flat: np.ndarray
    orig_shape: tuple
    padded_shape: tuple
    fmt: Format


def prepare(data: np.ndarray, fmt: Format, dtype_name: str) -> PreparedArg:
    """按 fmt 对整块 tensor 做 pad + flatten（全程 double）。

    N-D tensor 的 batch 维度会被保留在 padded_shape 里，flatten 后仍是 C-order
    外层 batch。ZZ 的内层 2D 是行优先，NN 的内层 2D 是列优先。

    自动 squeeze 约定:
        对于 ndim >= 2 的输入，如果除末维外所有维都是 1（`shape[:-1]` 全 1），
        框架把它当作长度 `shape[-1]` 的 1D 处理。典型场景：linear 的 bias 常以
        `(1, N)` 形状传入，但语义就是 1D 偏置。这样 op 作者不用管这种"行向量
        2D 包装"。
    """
    data = np.ascontiguousarray(data, dtype=np.double)
    # 自动 squeeze 成 1D: (1,)*n + (D,) → (D,)
    if data.ndim >= 2 and all(d == 1 for d in data.shape[:-1]):
        squeezed = data.reshape(-1)
        result = _prepare_core(squeezed, fmt, dtype_name)
        # 保留原始 shape 在 orig_shape 里，方便 op 读原形
        return PreparedArg(result.flat, data.shape, result.padded_shape, result.fmt)
    return _prepare_core(data, fmt, dtype_name)


def _prepare_core(data: np.ndarray, fmt: Format, dtype_name: str) -> PreparedArg:
    if fmt == Format.ZZ:
        return _prep_zz(data, dtype_name)
    if fmt == Format.NN:
        return _prep_nn(data, dtype_name)
    if fmt == Format.ND:
        return _prep_nd(data, dtype_name)
    raise ValueError(f"prepare: unsupported fmt {fmt!r}")


# ============================================================
# ZZ: row-major 2D block
# ============================================================

def _prep_zz(data: np.ndarray, dtype_name: str) -> PreparedArg:
    bh, bw = get_block_shape(dtype_name, Format.ZZ)
    if data.ndim == 0:
        raise ValueError("Format.ZZ 不支持 0-D 标量")
    if data.ndim == 1:
        return _pad_1d(data, bw, Format.ZZ)
    # ≥2D: last-2-dim pad 到 (bh, bw), 保留 batch, 行优先 flatten
    *batch, h, w = data.shape
    ph, pw = pad_dim(h, bh), pad_dim(w, bw)
    if (ph, pw) == (h, w):
        return PreparedArg(data.reshape(-1).copy(), data.shape, data.shape, Format.ZZ)
    padded_shape = (*batch, ph, pw)
    padded = np.zeros(padded_shape, dtype=np.double)
    padded[..., :h, :w] = data
    return PreparedArg(padded.reshape(-1).copy(), data.shape, padded_shape, Format.ZZ)


# ============================================================
# NN: col-major 2D block
# ============================================================

def _prep_nn(data: np.ndarray, dtype_name: str) -> PreparedArg:
    bh, bw = get_block_shape(dtype_name, Format.NN)
    if data.ndim == 0:
        raise ValueError("Format.NN 不支持 0-D 标量")
    if data.ndim == 1:
        return _pad_1d(data, bw, Format.NN)
    # ≥2D: last-2-dim pad 到 (bh, bw), 保留 batch, 每个 batch 片列优先 flatten
    *batch, h, w = data.shape
    ph, pw = pad_dim(h, bh), pad_dim(w, bw)
    if (ph, pw) == (h, w):
        padded = data
        orig_equals_padded = True
    else:
        padded = np.zeros((*batch, ph, pw), dtype=np.double)
        padded[..., :h, :w] = data
        orig_equals_padded = False

    # 每个 batch 片列优先 = 把内层 (ph, pw) 做 transpose 再 C-order flatten
    # swapaxes 返回 view, ascontiguousarray 保证连续
    col_major = np.ascontiguousarray(padded.swapaxes(-1, -2))  # shape: (*batch, pw, ph)
    flat = col_major.reshape(-1).copy()
    padded_shape = data.shape if orig_equals_padded else (*batch, ph, pw)
    return PreparedArg(flat, data.shape, padded_shape, Format.NN)


# ============================================================
# ND: natural dim, 仅末维 pad
# ============================================================

def _prep_nd(data: np.ndarray, dtype_name: str) -> PreparedArg:
    """ND 规则：pad 末维到 `bh_zz` (= bw_nn)，前面维度原样，C-order flatten。

    当前 4 个 op 都不用 ND；保留规则供将来 elementwise-over-last-dim 类 op 使用。
    """
    q = get_block_shape(dtype_name, Format.ZZ)[0]  # bh_zz
    if data.ndim == 0:
        last = 1
        data = data.reshape(1)
    else:
        last = data.shape[-1]
    padded_last = pad_dim(last, q)
    if padded_last == last:
        return PreparedArg(data.reshape(-1).copy(), data.shape, data.shape, Format.ND)
    padded_shape = (*data.shape[:-1], padded_last)
    padded = np.zeros(padded_shape, dtype=np.double)
    padded[..., :last] = data
    return PreparedArg(padded.reshape(-1).copy(), data.shape, padded_shape, Format.ND)


# ============================================================
# 辅助
# ============================================================

def _pad_1d(data: np.ndarray, quantum: int, fmt: Format) -> PreparedArg:
    """1D pad 到 quantum，直接 flat（1D 情况下 row-major 和 col-major 等价）。"""
    n = int(data.shape[0])
    pn = pad_dim(n, quantum)
    if pn == n:
        return PreparedArg(data.copy(), (n,), (pn,), fmt)
    flat = np.zeros(pn, dtype=np.double)
    flat[:n] = data
    return PreparedArg(flat, (n,), (pn,), fmt)
