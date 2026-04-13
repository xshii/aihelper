"""LayoutMixin — 布局转换能力。

block + padding 逻辑。block_shape 从 golden.manifest 查。
纯函数在 core/block.py，这里只有 Mixin 类和 infer_format。
"""

from __future__ import annotations

import torch

from ..core.enums import Format
from ..core.block import to_block, from_block


class LayoutMixin:
    """布局转换：ND ↔ ZZ / NN（block + padding）。"""

    # 宿主类提供的属性（DataPipe）
    _dtype_name: str
    _fmt: Format
    _tensor: torch.Tensor
    _orig_shape: tuple
    def _log(self, msg: str) -> None: ...

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

        if self._fmt != Format.ND:
            self._tensor = from_block(
                self._tensor, self._dtype_name, self._fmt,
                self._orig_shape,
            )

        if target_fmt != Format.ND:
            self._tensor = to_block(self._tensor, self._dtype_name, target_fmt)

        old_fmt = self._fmt
        self._fmt = target_fmt
        self._log(f"layout({old_fmt} → {target_fmt})")
        return self


def infer_format(t: torch.Tensor) -> Format:
    """根据 shape 推断默认内存格式。只看最后两维。"""
    match t.ndim:
        case 0 | 1:
            return Format.ND
        case _:
            last_two = t.shape[-2:]
            return Format.ND if any(s == 1 for s in last_two) else Format.ZZ
