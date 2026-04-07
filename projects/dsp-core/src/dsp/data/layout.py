"""LayoutMixin — 布局转换能力。

block + padding 逻辑。block_shape 从 golden.manifest 查。
"""

from __future__ import annotations

import torch

from ..core.enums import Format


class LayoutMixin:
    """布局转换：ND ↔ ZZ / NN（block + padding）。"""

    def layout(self, target_fmt: Format):
        """布局转换。返回 self（链式）。

        Args:
            target_fmt: Format.ND / Format.ZZ / Format.NN

        Example:
            pipe.layout(Format.ZZ).export("blocked.txt").layout(Format.ND)
        """
        target_fmt = Format(target_fmt)
        if target_fmt == self._fmt:
            return self

        from ..golden.manifest import get_block_shape

        if self._fmt != Format.ND:
            self._tensor = _from_block(
                self._tensor, self._fmt,
                get_block_shape(self._dtype_name, self._fmt),
                self._orig_shape,
            )

        if target_fmt != Format.ND:
            block_shape = get_block_shape(self._dtype_name, target_fmt)
            self._tensor = _to_block(self._tensor, target_fmt, block_shape)

        old_fmt = self._fmt
        self._fmt = target_fmt
        self._log(f"layout({old_fmt} → {target_fmt})")
        return self


# ============================================================
# Block 格式转换（纯函数）
# ============================================================

def _pad_to_block(t: torch.Tensor, block_shape: tuple) -> torch.Tensor:
    if t.ndim < 2:
        return t
    h, w = t.shape[-2], t.shape[-1]
    bh, bw = block_shape
    pad_h = (bh - h % bh) % bh
    pad_w = (bw - w % bw) % bw
    if pad_h == 0 and pad_w == 0:
        return t
    return torch.nn.functional.pad(t, (0, pad_w, 0, pad_h), value=0)


def _to_block(t: torch.Tensor, fmt: str, block_shape: tuple) -> torch.Tensor:
    """nd → blocked（zz 或 nn，当前共享同一分块逻辑）。"""
    if t.ndim < 2:
        return t
    padded = _pad_to_block(t, block_shape)
    h, w = padded.shape[-2], padded.shape[-1]
    bh, bw = block_shape
    blocked = padded.reshape(*padded.shape[:-2], h // bh, bh, w // bw, bw)
    blocked = blocked.permute(*range(len(padded.shape) - 2), -4, -2, -3, -1)
    return blocked.contiguous()


def _from_block(data: torch.Tensor, fmt: str, block_shape: tuple,
                orig_shape: tuple) -> torch.Tensor:
    """blocked → nd（去 padding）。"""
    if len(orig_shape) < 2:
        return data.reshape(orig_shape)
    bh, bw = block_shape
    h, w = orig_shape[-2], orig_shape[-1]
    padded_h = h + (bh - h % bh) % bh
    padded_w = w + (bw - w % bw) % bw
    n_bh = padded_h // bh
    n_bw = padded_w // bw
    blocked = data.reshape(*orig_shape[:-2], n_bh, n_bw, bh, bw)
    blocked = blocked.permute(*range(len(orig_shape) - 2), -4, -2, -3, -1)
    unblocked = blocked.reshape(*orig_shape[:-2], padded_h, padded_w)
    return unblocked[..., :h, :w].contiguous()


def infer_format(t: torch.Tensor) -> Format:
    """根据 shape 推断默认内存格式。只看最后两维。"""
    match t.ndim:
        case 0 | 1:
            return Format.ND
        case _:
            last_two = t.shape[-2:]
            return Format.ND if any(s == 1 for s in last_two) else Format.ZZ
