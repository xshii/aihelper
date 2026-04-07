"""类型编解码器: 自定义格式 ↔ torch float 的转换。

三个方法全部通过 golden C 的 convert 函数实现。
Python 层不知道 DUT 格式的内部细节（frac_bits 等），全交给 C++。

新增 codec 用 __init_subclass__:
    class BFP16Codec(GoldenCCodec, dtype=bfp16):  # ← 定义即注册，无需实现任何方法
        pass
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import torch

from .dtype import DSPDtype


class TypeCodec(ABC):
    """编解码器基类。"""

    @abstractmethod
    def to_float(self, raw: torch.Tensor, dtype: DSPDtype) -> torch.Tensor: ...

    @abstractmethod
    def from_float(self, t: torch.Tensor, dtype: DSPDtype) -> torch.Tensor: ...

    @abstractmethod
    def fake_quantize(self, t: torch.Tensor, dtype: DSPDtype) -> torch.Tensor: ...


# ============================================================
# 注册表
# ============================================================

_CODEC_REGISTRY: dict[str, TypeCodec] = {}


def register_codec(dtype: DSPDtype, codec: TypeCodec):
    _CODEC_REGISTRY[dtype.name] = codec


def get_codec(dtype: DSPDtype) -> TypeCodec:
    codec = _CODEC_REGISTRY.get(dtype.name)
    if codec is None:
        raise TypeError(
            f"未注册类型 {dtype} 的编解码器。"
            f"已注册: {list(_CODEC_REGISTRY.keys())}"
        )
    return codec


# ============================================================
# PassthroughCodec: float32 / float64，无需转换
# ============================================================

class PassthroughCodec(TypeCodec):
    """直通 codec: float32 / float64。"""

    def to_float(self, raw, dtype):
        return raw.float() if dtype.torch_dtype == torch.float32 else raw.double()

    def from_float(self, t, dtype):
        return t.to(dtype.torch_dtype)

    def fake_quantize(self, t, dtype):
        return t


# ============================================================
# GoldenCCodec: 全部走 golden C convert，无 Python fallback
# ============================================================

class GoldenCCodec(TypeCodec):
    """通过 golden C convert 函数实现的 codec。

    所有转换调 golden.convert(data, src_type, dst_type)。
    Python 层不知道 DUT 格式细节，全交给 C++。
    golden C 不可用时直接报错。

    子类用 __init_subclass__ 自动注册，无需实现任何方法:
        class BFP16Codec(GoldenCCodec, dtype=bfp16):
            pass
    """

    _converter = None
    _is_available = None

    @classmethod
    def set_golden_converter(cls, converter, is_available_fn):
        """由 golden 模块注入 convert 函数。core 不直接 import golden。"""
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
        flat = _to_flat_float(raw)
        out = self._converter(flat, dtype.name, "float32")
        return _from_flat_float(out, raw.shape, raw.is_complex())

    def from_float(self, t, dtype):
        self._require_golden()
        flat = _to_flat_float(t)
        out = self._converter(flat, "float32", dtype.name)
        return _from_flat_float(out, t.shape, t.is_complex())

    def fake_quantize(self, t, dtype):
        self._require_golden()
        flat = _to_flat_float(t)
        quantized = self._converter(flat, "float32", dtype.name)
        result_np = self._converter(quantized, dtype.name, "float32")
        result = _from_flat_float(result_np, t.shape, t.is_complex())
        if t.requires_grad:
            result = t + (result - t).detach()
        return result


# ============================================================
# Complex ↔ float 辅助（interleaved real/imag）
# ============================================================

def _to_flat_float(t: torch.Tensor):
    """tensor → flat float32 numpy。complex 展开为 interleaved [re, im, re, im, ...]。"""
    import numpy as np
    if t.is_complex():
        real = t.real.detach().cpu().float().numpy().flatten()
        imag = t.imag.detach().cpu().float().numpy().flatten()
        return np.stack([real, imag], axis=-1).flatten().astype(np.float32)
    return t.detach().cpu().float().numpy().flatten().astype(np.float32)


def _from_flat_float(data, shape: tuple, is_complex: bool):
    """flat float32 numpy → tensor。complex 从 interleaved 还原。"""
    result = torch.from_numpy(data.copy())
    if is_complex:
        real = result[0::2]
        imag = result[1::2]
        return torch.complex(real, imag).reshape(shape)
    return result.reshape(shape)


# ============================================================
# 内置 codec（定义即注册，无需实现任何方法）
# ============================================================

from . import dtype as _dtypes  # noqa: E402


class IQ16Codec(GoldenCCodec, dtype=_dtypes.iq16):
    pass


class IQ32Codec(GoldenCCodec, dtype=_dtypes.iq32):
    pass


# Passthrough 手动注册
register_codec(_dtypes.float32, PassthroughCodec())
register_codec(_dtypes.float64, PassthroughCodec())
