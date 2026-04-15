"""Block 类型定义 + 格式转换 — core 层，无上层依赖。

类型:
    BlockShape(rows, cols)        — 一种 format 下的 block 尺寸
    TypeInfo(zz, nn)              — 一种 DUT 类型的 block 信息
    BLOCK_TYPES                   — {DType枚举: TypeInfo} 全局表

函数:
    get_block_shape(dtype_name, fmt)        — 查 block shape
    pad_dim(dim, block)                     — 单维度向上对齐
    pad_to_block(t, block_shape)            — 2D tensor pad 到 block 对齐
    to_block(t, fmt, block_shape)           — nd → blocked (torch)
    from_block(data, fmt, ...)              — blocked → nd (torch)
    format_to_dut(data, dtype_name, fmt)    — numpy 2D → pad → block → flat
    format_from_dut(flat, dtype_name, ...)  — flat → reshape → crop

## 存储顺序

行优先（row-major）和列优先（col-major）定义:

    原始矩阵 (2×3):
    [ a  b  c ]     row0
    [ d  e  f ]     row1
      c0 c1 c2

    行优先 flat: [a, b, c, d, e, f]    — 逐行存储
    列优先 flat: [a, d, b, e, c, f]    — 逐列存储

    行优先索引: mat[row, col] = flat[row * ncols + col]
    列优先索引: mat[row, col] = flat[col * nrows + row]

## Block 布局

硬件有两级分块:
  - subblock: 128-bit 寄存器，BF8 = 16 元素，BF16 = 8 元素
  - block: 一次读取的最小 2D tile，由多个 subblock 组成

两种 block 布局 (以 4×4 矩阵、block_shape=(2,2) 为例):

    原始 (ND):                   4 个 block:
    [ a  b | c  d ]              A=[a,b,e,f]  B=[c,d,g,h]
    [ e  f | g  h ]              C=[i,j,m,n]  D=[k,l,o,p]
    ------+-------
    [ i  j | k  l ]
    [ m  n | o  p ]

    ZZ (行优先): block 间行优先 + block 内行优先
      flat: [a,b,e,f, c,d,g,h, i,j,m,n, k,l,o,p]
             ──A──    ──B──    ──C──    ──D──

    NN (列优先): block 间列优先 + block 内列优先
      flat: [a,e,b,f, i,m,j,n, c,g,d,h, k,o,l,p]
             ──A──    ──C──    ──B──    ──D──

## Golden C 计算路径

golden C 参考实现不做 block reorder，只做 pad + 按存储顺序 flatten:
  - ZZ: pad → 行优先 flatten → C 函数用 a[m*K+k] 索引
  - NN: pad → 列优先 flatten → C 函数用 b[col*nrows+row] 索引

import/export DUT 数据时需要完整的 block reorder + padding。

不满 block 的 shape 自动 padding 0。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

import numpy as np
import torch

from .enums import Format
from .dtype import DType


# ============================================================
# Block 类型定义
# ============================================================

@dataclass(frozen=True)
class BlockShape:
    """一种 DUT 类型在某个 Format 下的 block shape。"""
    rows: int
    cols: int

    def __iter__(self):
        return iter((self.rows, self.cols))


@dataclass(frozen=True)
class TypeInfo:
    """一种 DUT 类型的 block 信息。"""
    zz: BlockShape
    nn: BlockShape

    def block_shape(self, fmt: Format) -> BlockShape:
        if str(fmt) == str(Format.ZZ):
            return self.zz
        elif str(fmt) == str(Format.NN):
            return self.nn
        return self.zz


BLOCK_TYPES: dict[str, TypeInfo] = {
    DType.DUT.BF8:     TypeInfo(zz=BlockShape(32, 16), nn=BlockShape(16, 32)),
    DType.DUT.BF16:    TypeInfo(zz=BlockShape(32, 16), nn=BlockShape(16, 32)),
    DType.REAL.DOUBLE:  TypeInfo(zz=BlockShape(4, 4),   nn=BlockShape(4, 4)),
}


@cache
def get_block_shape(dtype_name: str, fmt: str | Format) -> tuple[int, int]:
    """查 (dtype, format) 对应的 block shape。返回 (rows, cols)。"""
    info = BLOCK_TYPES.get(dtype_name)
    if info is not None:
        bs = info.block_shape(Format(fmt))
        return (bs.rows, bs.cols)
    return (8, 8)


# ============================================================
# Padding
# ============================================================

def pad_dim(dim: int, block: int) -> int:
    """单维度向上对齐到 block 的倍数。"""
    return dim + (block - dim % block) % block


def pad_to_block(t: torch.Tensor, dtype_name: str, fmt: str | Format) -> torch.Tensor:
    """2D tensor pad 到 block 对齐（补零）。"""
    if t.ndim < 2:
        return t
    bh, bw = get_block_shape(dtype_name, fmt)
    h, w = t.shape[-2], t.shape[-1]
    ph, pw = pad_dim(h, bh), pad_dim(w, bw)
    if ph == h and pw == w:
        return t
    return torch.nn.functional.pad(t, (0, pw - w, 0, ph - h), value=0)


# ============================================================
# torch tensor ↔ blocked
# ============================================================

def _block_permute(fmt: str, ndim_prefix: int) -> list[int]:
    prefix = list(range(ndim_prefix))
    if str(fmt) == str(Format.ZZ):
        return prefix + [-4, -2, -3, -1]
    else:
        return prefix + [-2, -4, -1, -3]


def _block_unpermute(fmt: str, ndim_prefix: int) -> list[int]:
    prefix = list(range(ndim_prefix))
    if str(fmt) == str(Format.ZZ):
        return prefix + [-4, -2, -3, -1]
    else:
        return prefix + [-3, -1, -4, -2]


def to_block(t: torch.Tensor, dtype_name: str, fmt: str | Format) -> torch.Tensor:
    """nd → blocked。ZZ 行优先，NN 列优先。"""
    if t.ndim < 2:
        return t
    bh, bw = get_block_shape(dtype_name, fmt)
    padded = pad_to_block(t, dtype_name, fmt)
    h, w = padded.shape[-2], padded.shape[-1]
    blocked = padded.reshape(*padded.shape[:-2], h // bh, bh, w // bw, bw)
    perm = _block_permute(str(fmt), len(padded.shape) - 2)
    blocked = blocked.permute(*perm)
    return blocked.contiguous()


def from_block(data: torch.Tensor, dtype_name: str, fmt: str | Format,
               orig_shape: tuple[int, ...]) -> torch.Tensor:
    """blocked → nd（去 padding）。"""
    if len(orig_shape) < 2:
        return data.reshape(orig_shape)
    bh, bw = get_block_shape(dtype_name, fmt)
    h, w = orig_shape[-2], orig_shape[-1]
    ph, pw = pad_dim(h, bh), pad_dim(w, bw)
    n_bh = ph // bh
    n_bw = pw // bw

    # to_block 先 reshape 成 (n_bh, bh, n_bw, bw) 再 permute
    # 存储后的 shape 是 permute 后的维度排列
    orig_4 = (n_bh, bh, n_bw, bw)
    perm = _block_permute(str(fmt), 0)
    pos_perm = [p + 4 for p in perm]
    stored_4 = tuple(orig_4[pos_perm[i]] for i in range(4))

    blocked = data.reshape(*orig_shape[:-2], *stored_4)
    unperm = _block_unpermute(str(fmt), len(orig_shape) - 2)
    blocked = blocked.permute(*unperm)
    unblocked = blocked.reshape(*orig_shape[:-2], ph, pw)
    return unblocked[..., :h, :w].contiguous()


# ============================================================
# numpy ↔ blocked flat（C binding 用）
# ============================================================

def format_to_dut(data: np.ndarray, dtype_name: str, fmt: str) -> tuple[np.ndarray, tuple]:
    """numpy 2D → pad → block reorder → flat。给 C binding 用。

    Returns:
        (flat_blocked, orig_shape)
    """
    if data.ndim < 2:
        return data.flatten().copy(), data.shape

    orig_shape = data.shape
    bh, bw = get_block_shape(dtype_name, fmt)

    h, w = data.shape[-2], data.shape[-1]
    ph, pw = pad_dim(h, bh), pad_dim(w, bw)
    if ph != h or pw != w:
        padded = np.zeros((*data.shape[:-2], ph, pw), dtype=data.dtype)
        padded[..., :h, :w] = data
    else:
        padded = data

    t = torch.from_numpy(padded)
    blocked = to_block(t, dtype_name, fmt)
    return blocked.numpy().reshape(-1).copy(), orig_shape


def format_from_dut(flat: np.ndarray, dtype_name: str, fmt: str,
                    orig_shape: tuple) -> np.ndarray:
    """C 输出 flat → reshape(padded) → crop → 原始 shape。"""
    if len(orig_shape) < 2:
        return flat.reshape(orig_shape)

    h, w = orig_shape[-2], orig_shape[-1]
    batch_shape = orig_shape[:-2]
    bh, bw = get_block_shape(dtype_name, fmt)
    ph, pw = pad_dim(h, bh), pad_dim(w, bw)

    padded = flat.reshape(*batch_shape, ph, pw)
    return padded[..., :h, :w].copy()


