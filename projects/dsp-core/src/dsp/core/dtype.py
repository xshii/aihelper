"""DSP 类型系统 — 运行时 dtype + 分类枚举 + codec。

运行时 dtype:
    dsp.core.bf16 → DSPDtype(name="bf16", torch_dtype=torch.bfloat16, subblock_size=8)

分类枚举:
    DType.DUT.BF16 = "bf16"
    DType.ACC.Q12_22 = "q12.22"

用法:
    from dsp.core.dtype import DType, bf16, get_dtype
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np
import torch
from dataclasses import dataclass
from abc import ABC, abstractmethod

from .enums import _StrEnum


# ============================================================
# 分类枚举 — ComputeKey 用
# ============================================================

class DType:
    class REAL(_StrEnum):
        DOUBLE = "double"

    class DUT(_StrEnum):
        BF8 = "bf8"
        BF16 = "bf16"

    class ACC(_StrEnum):
        Q12_22 = "q12.22"


# ============================================================
# 运行时 dtype
# ============================================================

@dataclass(frozen=True)
class DSPDtype:
    name: str
    torch_dtype: torch.dtype
    subblock_size: int = 1  # 128-bit 寄存器内的元素数

    def __repr__(self):
        return f"dsp.{self.name}"

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, DSPDtype):
            return self.name == other.name
        return NotImplemented


# 预定义 dtype
bf8 = DSPDtype(name="bf8", torch_dtype=torch.float8_e4m3fn, subblock_size=16)
bf16 = DSPDtype(name="bf16", torch_dtype=torch.bfloat16, subblock_size=8)
double = DSPDtype(name="double", torch_dtype=torch.double)

# dtype 注册表
_ALL_DTYPES: dict[str, DSPDtype] = {d.name: d for d in [bf8, bf16, double]}


def get_dtype(name: str) -> DSPDtype:
    d = _ALL_DTYPES.get(name)
    if d is None:
        raise ValueError(f"未知 dtype '{name}'。已注册: {list(_ALL_DTYPES.keys())}")
    return d


def dtype_from_torch(torch_dtype: torch.dtype) -> Optional[DSPDtype]:
    """按 torch.dtype 反查 DSPDtype。未注册返回 None。"""
    for d in _ALL_DTYPES.values():
        if d.torch_dtype == torch_dtype:
            return d
    return None


def register_dtype(dtype: DSPDtype):
    _ALL_DTYPES[dtype.name] = dtype


def list_dtypes() -> list[str]:
    return list(_ALL_DTYPES.keys())


# ============================================================
# 类型编解码器: 自定义格式 ↔ torch float
# ============================================================

class TypeCodec(ABC):
    @abstractmethod
    def to_double(self, raw: torch.Tensor, dtype: DSPDtype) -> torch.Tensor: ...

    @abstractmethod
    def from_double(self, t: torch.Tensor, dtype: DSPDtype) -> torch.Tensor: ...

    @abstractmethod
    def fake_quantize(self, t: torch.Tensor, dtype: DSPDtype) -> torch.Tensor: ...


_CODEC_REGISTRY: dict[str, TypeCodec] = {}


def register_codec(dtype: DSPDtype, codec: TypeCodec):
    _CODEC_REGISTRY[dtype.name] = codec


def get_codec(dtype: DSPDtype) -> TypeCodec:
    codec = _CODEC_REGISTRY.get(dtype.name)
    if codec is None:
        raise TypeError(f"未注册类型 {dtype} 的编解码器。已注册: {list(_CODEC_REGISTRY.keys())}")
    return codec


class PassthroughCodec(TypeCodec):
    """double 等标准浮点，无需转换。"""
    def to_double(self, raw: torch.Tensor, _dtype: DSPDtype) -> torch.Tensor:
        return raw.double()

    def from_double(self, t: torch.Tensor, dtype: DSPDtype) -> torch.Tensor:
        return t.to(dtype.torch_dtype)

    def fake_quantize(self, t: torch.Tensor, _dtype: DSPDtype) -> torch.Tensor:
        return t


def _to_np(t: torch.Tensor) -> np.ndarray:
    """torch → flat double numpy。"""
    return t.detach().cpu().double().numpy().flatten().astype(np.double)


_ConverterFn = Callable[[np.ndarray, str, str], np.ndarray]


class GoldenCCodec(TypeCodec):
    """通过 golden C convert 函数实现的 codec。"""

    _converter: Optional[_ConverterFn] = None
    _is_available: Optional[Callable[[], bool]] = None

    @classmethod
    def set_golden_converter(cls, converter: _ConverterFn, is_available_fn: Callable[[], bool]) -> None:
        cls._converter = staticmethod(converter)  # type: ignore[assignment]
        cls._is_available = staticmethod(is_available_fn)  # type: ignore[assignment]

    def _require_golden(self) -> None:
        if self._is_available is None or not self._is_available():
            from .errors import GoldenNotAvailable
            raise GoldenNotAvailable("codec 需要 golden C。")

    def to_double(self, raw: torch.Tensor, dtype: DSPDtype) -> torch.Tensor:
        self._require_golden()
        assert self._converter is not None
        out = self._converter(_to_np(raw), dtype.name, "double")
        return torch.from_numpy(out.copy()).reshape(raw.shape)

    def from_double(self, t: torch.Tensor, dtype: DSPDtype) -> torch.Tensor:
        self._require_golden()
        assert self._converter is not None
        out = self._converter(_to_np(t), "double", dtype.name)
        return torch.from_numpy(out.copy()).reshape(t.shape)

    def fake_quantize(self, t: torch.Tensor, dtype: DSPDtype) -> torch.Tensor:
        self._require_golden()
        assert self._converter is not None
        from .block import pad_dim
        flat = _to_np(t)
        n = flat.size
        # C 侧 dsp_convert 要求 count 是 subblock 整数倍 → 补零对齐后再 trim
        n_pad = pad_dim(n, dtype.subblock_size)
        if n_pad != n:
            flat = np.concatenate([flat, np.zeros(n_pad - n, dtype=np.double)])
        quantized = self._converter(flat, "double", dtype.name)
        result_np = self._converter(quantized, dtype.name, "double")[:n]
        result = torch.from_numpy(result_np.copy()).reshape(t.shape).double()
        if t.requires_grad:
            result = t + (result - t).detach()
        return result


# 内置 codec 注册
_golden_codec = GoldenCCodec()
register_codec(bf8, _golden_codec)
register_codec(bf16, _golden_codec)
register_codec(double, PassthroughCodec())
