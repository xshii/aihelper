"""DataPipe — 链式数据管线。

通过 Mixin 组合能力：
    ConvertMixin  — 值转换（调 golden.convert）
    LayoutMixin   — 布局转换（block + padding）
    IOMixin       — 文件读写（hex txt）
    CompareMixin  — 数据比对
    VizMixin      — 可视化

用法:
    pipe = DataPipe.from_tensor(x, dtype="int16")
    pipe.convert("float32").layout("zz").export("out.txt")

    diff = DataPipe.load("a.txt").compare(DataPipe.load("b.txt"))
"""

from __future__ import annotations

import torch

from ..core.enums import Format
from .convert import ConvertMixin
from .layout import LayoutMixin
from .io import IOMixin
from .compare import CompareMixin
from .viz import VizMixin


class DataPipe(ConvertMixin, LayoutMixin, IOMixin, CompareMixin, VizMixin):
    """数据管线主类。所有能力通过 Mixin 组合。

    内部状态:
        _tensor:     torch.Tensor
        _dtype_name: str（数据类型名）
        _fmt:        Format（布局格式）
        _orig_shape: tuple（block 前原始 shape）
        _history:    list（变换历史）
    """

    def __init__(self, tensor: torch.Tensor, dtype: str = None, fmt: Format = Format.ND):
        self._tensor = tensor
        self._dtype_name = dtype or "float32"
        self._fmt = fmt
        self._orig_shape = tuple(tensor.shape)
        self._history = []

    def _log(self, action: str):
        self._history.append(action)

    @property
    def tensor(self) -> torch.Tensor:
        return self._tensor

    @property
    def dtype_name(self) -> str:
        return self._dtype_name

    @property
    def fmt(self) -> Format:
        return self._fmt

    @property
    def shape(self) -> tuple:
        return self._orig_shape

    @property
    def history(self) -> list[str]:
        return list(self._history)

    def clone(self) -> DataPipe:
        """深拷贝。"""
        p = DataPipe(self._tensor.clone(), self._dtype_name, self._fmt)
        p._orig_shape = self._orig_shape
        p._history = list(self._history)
        return p

    def to_tensor(self) -> torch.Tensor:
        """取出 torch.Tensor（终止链）。"""
        return self._tensor

    def __repr__(self):
        return (
            f"DataPipe(dtype={self._dtype_name}, fmt={self._fmt}, "
            f"shape={self._orig_shape}, steps={len(self._history)})"
        )
