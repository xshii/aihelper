"""DSP 自定义 dtype 系统。

dsp.iq16 / dsp.float32 等，形似 torch.float32，但携带定点/量化元数据。
torch.dtype 不可从 Python 扩展，所以我们用独立的 DSPDtype 对象 + 元数据。

用法:
    import dsp
    a = dsp.randn(100, dtype=dsp.iq16)
    a.dtype  # dsp.iq16
"""

from __future__ import annotations

import torch
from dataclasses import dataclass


@dataclass(frozen=True)
class DSPDtype:
    """一种 DSP 数据类型的描述。

    形似 torch.dtype —— 标记对象，传给 dsp.data.randn() 等。
    DUT 格式的细节（frac_bits 等）由 golden C 处理，Python 层不感知。
    """

    name: str                   # 显示名: "iq16", "float32", ...
    torch_dtype: torch.dtype    # 底层 torch 存储类型
    bits: int                   # 总位宽
    signed: bool = True         # 有符号
    is_complex: bool = False    # IQ 类型 = True

    def __repr__(self):
        return f"dsp.{self.name}"

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, DSPDtype):
            return self.name == other.name
        return NotImplemented


# ============================================================
# 预定义 dtype（用户直接用 dsp.iq16 等）
# ============================================================

iq16 = DSPDtype(
    name="iq16",
    torch_dtype=torch.complex64,
    bits=16, is_complex=True,
)

iq32 = DSPDtype(
    name="iq32",
    torch_dtype=torch.complex128,
    bits=32, is_complex=True,
)

float32 = DSPDtype(
    name="float32",
    torch_dtype=torch.float32,
    bits=32,
)

float64 = DSPDtype(
    name="float64",
    torch_dtype=torch.float64,
    bits=64,
)


# dtype 注册表（可动态添加新 dtype）
_ALL_DTYPES: dict[str, DSPDtype] = {}


def register_dtype(dtype: DSPDtype):
    """注册一个新的 DSPDtype。"""
    _ALL_DTYPES[dtype.name] = dtype


def get_dtype(name: str) -> DSPDtype:
    """按名称查找 dtype。"""
    d = _ALL_DTYPES.get(name)
    if d is None:
        raise ValueError(f"未知 dtype '{name}'。已注册: {list(_ALL_DTYPES.keys())}")
    return d


def list_dtypes() -> list[str]:
    """列出所有已注册的 dtype 名称。"""
    return list(_ALL_DTYPES.keys())


# 注册预定义 dtype
for _d in [iq16, iq32, float32, float64]:
    register_dtype(_d)
