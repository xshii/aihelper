"""类型编解码器: 自定义格式 ↔ torch float 的转换。

DUT 格式的细节由 golden C 处理，Python 不感知。

新增 codec 用 __init_subclass__:
    class BFP16Codec(GoldenCCodec, dtype=bfp16):
        pass
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import torch

from .dtype import DSPDtype


class TypeCodec(ABC):
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
            f"未注册类型 {dtype} 的编解码器。已注册: {list(_CODEC_REGISTRY.keys())}"
        )
    return codec


# ============================================================
# PassthroughCodec: float32 / float64，无需转换
# ============================================================

class PassthroughCodec(TypeCodec):
    def to_float(self, raw, dtype):
        return raw.float()

    def from_float(self, t, dtype):
        return t.to(dtype.torch_dtype)

    def fake_quantize(self, t, dtype):
        return t


# ============================================================
# GoldenCCodec: 全部走 golden C convert
# ============================================================

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
        # 转回原始 torch dtype（int16 等）
        result = result.to(dtype.torch_dtype)
        if t.requires_grad:
            result = t + (result - t).detach()
        return result


# ============================================================
# 内置 codec（定义即注册）
# ============================================================

from . import dtype as _dtypes  # noqa: E402


class Int16Codec(GoldenCCodec, dtype=_dtypes.int16):
    pass


class Int8Codec(GoldenCCodec, dtype=_dtypes.int8):
    pass


class Int32Codec(GoldenCCodec, dtype=_dtypes.int32):
    pass


register_codec(_dtypes.float32, PassthroughCodec())
register_codec(_dtypes.float64, PassthroughCodec())


# ============================================================
# 辅助函数
# ============================================================

def _to_flat_float(t: torch.Tensor):
    """tensor → flat float32 numpy array。"""
    import numpy as np
    return t.detach().cpu().float().numpy().flatten().astype(np.float32)
