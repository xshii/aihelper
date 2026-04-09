"""DSP 自定义 dtype 系统。

dsp.int16 / dsp.float32 等，形似 torch.float32，但携带 DSP 元数据。

用法:
    import dsp
    a = dsp.data.randn(100, dtype=dsp.core.int16)
"""

from __future__ import annotations

import torch
from dataclasses import dataclass


@dataclass(frozen=True)
class DSPDtype:
    """一种 DSP 数据类型的描述。

    name: 显示名（"int16", "float32", ...）
    torch_dtype: 底层 torch 存储类型
    """

    name: str
    torch_dtype: torch.dtype

    def __repr__(self):
        return f"dsp.{self.name}"

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, DSPDtype):
            return self.name == other.name
        return NotImplemented


# ============================================================
# 预定义 dtype
# ============================================================

int8 = DSPDtype(name="int8", torch_dtype=torch.int8)
int16 = DSPDtype(name="int16", torch_dtype=torch.int16)
int32 = DSPDtype(name="int32", torch_dtype=torch.int32)
float32 = DSPDtype(name="float32", torch_dtype=torch.float32)
float64 = DSPDtype(name="float64", torch_dtype=torch.float64)


# dtype 注册表
_ALL_DTYPES: dict[str, DSPDtype] = {}


def register_dtype(dtype: DSPDtype):
    _ALL_DTYPES[dtype.name] = dtype


def get_dtype(name: str) -> DSPDtype:
    d = _ALL_DTYPES.get(name)
    if d is None:
        raise ValueError(f"未知 dtype '{name}'。已注册: {list(_ALL_DTYPES.keys())}")
    return d


def list_dtypes() -> list[str]:
    return list(_ALL_DTYPES.keys())


for _d in [int8, int16, int32, float32, float64]:
    register_dtype(_d)
