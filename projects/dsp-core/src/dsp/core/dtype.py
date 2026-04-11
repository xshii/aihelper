"""DSP 类型系统 — 运行时 dtype + 分类枚举，统一在此文件。

运行时 dtype:
    dsp.core.int16              → DSPDtype(name="int16", torch_dtype=torch.int16)
    用于创建 tensor、推导输出类型

分类枚举:
    DType.DUT.INT16 = "int16"   → 字符串标签，用于 ComputeKey 填类型槽位
    DType.ACC.Q12_22 = "q12.22" → ACC 累加器格式

两者通过 name 字符串桥接:
    DSPTensor._dsp_dtype.name == "int16" == DType.DUT.INT16

用法:
    from dsp.core.dtype import DType, int16, get_dtype
    a = dsp.data.randn(100, dtype=dsp.core.int16)
    ComputeKey(op="matmul", src0=DType.DUT.INT16, ...)
"""

from __future__ import annotations

import torch
from dataclasses import dataclass
from enum import Enum


# ============================================================
# 分类枚举 — ComputeKey 用
# ============================================================

class _StrEnum(str, Enum):
    def __str__(self):
        return self.value

    def __format__(self, format_spec):
        return self.value.__format__(format_spec)


class DType:
    """分级类型枚举。

    DType.REAL — 标准浮点（参考计算用）
    DType.DUT  — 芯片原生定点（数据存储）
    DType.ACC  — 累加器格式（只有 Q 格式）
    """

    class REAL(_StrEnum):
        FLOAT32 = "float32"
        FLOAT64 = "float64"

    class DUT(_StrEnum):
        INT8 = "int8"
        INT16 = "int16"
        INT32 = "int32"

    class ACC(_StrEnum):
        Q12_22 = "q12.22"
        Q8_26  = "q8.26"
        Q24_40 = "q24.40"


# ============================================================
# 运行时 dtype — tensor 创建用
# ============================================================


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


# ============================================================
# 类型编解码器: 自定义格式 ↔ torch float
# ============================================================

from abc import ABC, abstractmethod


class TypeCodec(ABC):
    @abstractmethod
    def to_float(self, raw: torch.Tensor, dtype: DSPDtype) -> torch.Tensor: ...

    @abstractmethod
    def from_float(self, t: torch.Tensor, dtype: DSPDtype) -> torch.Tensor: ...

    @abstractmethod
    def fake_quantize(self, t: torch.Tensor, dtype: DSPDtype) -> torch.Tensor: ...


_CODEC_REGISTRY: dict[str, TypeCodec] = {}


def register_codec(dtype: DSPDtype, codec: TypeCodec):
    _CODEC_REGISTRY[dtype.name] = codec


def get_codec(dtype: DSPDtype) -> TypeCodec:
    codec = _CODEC_REGISTRY.get(dtype.name)
    if codec is None:
        raise TypeError(
            f"未注册类型 {dtype} 的编解码器。已注册: {list(_CODEC_REGISTRY.keys())}"
        )
    return codec


class PassthroughCodec(TypeCodec):
    """float32 / float64，无需转换。"""
    def to_float(self, raw, dtype):
        return raw.float()

    def from_float(self, t, dtype):
        return t.to(dtype.torch_dtype)

    def fake_quantize(self, t, dtype):
        return t


class GoldenCCodec(TypeCodec):
    """通过 golden C convert 函数实现的 codec。

    子类用 __init_subclass__ 自动注册:
        class Int8Codec(GoldenCCodec, dtype=int8):
            pass
    """

    _converter = None
    _is_available = None

    @classmethod
    def set_golden_converter(cls, converter, is_available_fn):
        cls._converter = staticmethod(converter)
        cls._is_available = staticmethod(is_available_fn)

    def __init_subclass__(cls, dtype: DSPDtype = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if dtype is not None:
            register_codec(dtype, cls())

    def _require_golden(self):
        if self._is_available is None or not self._is_available():
            from .errors import GoldenNotAvailable
            raise GoldenNotAvailable("codec 需要 golden C。")

    def to_float(self, raw, dtype):
        self._require_golden()
        import numpy as np
        flat = raw.detach().cpu().float().numpy().flatten().astype(np.float32)
        out = self._converter(flat, dtype.name, "float32")
        return torch.from_numpy(out.copy()).reshape(raw.shape)

    def from_float(self, t, dtype):
        self._require_golden()
        import numpy as np
        flat = t.detach().cpu().float().numpy().flatten().astype(np.float32)
        out = self._converter(flat, "float32", dtype.name)
        return torch.from_numpy(out.copy()).reshape(t.shape)

    def fake_quantize(self, t, dtype):
        self._require_golden()
        import numpy as np
        flat = t.detach().cpu().float().numpy().flatten().astype(np.float32)
        quantized = self._converter(flat, "float32", dtype.name)
        result_np = self._converter(quantized, dtype.name, "float32")
        result = torch.from_numpy(result_np.copy()).reshape(t.shape)
        result = result.to(dtype.torch_dtype)
        if t.requires_grad:
            result = t + (result - t).detach()
        return result


# 内置 codec（定义即注册）
class Int8Codec(GoldenCCodec, dtype=int8): pass
class Int16Codec(GoldenCCodec, dtype=int16): pass
class Int32Codec(GoldenCCodec, dtype=int32): pass

register_codec(float32, PassthroughCodec())
register_codec(float64, PassthroughCodec())
