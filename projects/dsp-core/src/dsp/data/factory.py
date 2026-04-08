"""工厂函数 — 创建 DSPTensor（形似 torch.xxx）。

用法:
    import dsp
    a = dsp.data.randn(4, 8, dtype=dsp.core.iq16)
    b = dsp.data.zeros(10, dtype=dsp.core.float32)
"""

from __future__ import annotations

import torch

from ..core.tensor import DSPTensor
from ..core.dtype import DSPDtype
from ..core import float32 as _float32


# 依赖注入：context 启动时注入 randn 拦截器
_randn_interceptor = None


def set_randn_interceptor(interceptor):
    """由 context 模块注入。data 不直接 import context。"""
    global _randn_interceptor
    _randn_interceptor = interceptor


def tensor(data, dtype: DSPDtype = None, requires_grad: bool = False) -> DSPTensor:
    dtype = dtype or _float32
    return DSPTensor.create(
        torch.tensor(data, dtype=dtype.torch_dtype, requires_grad=requires_grad), dtype)


def zeros(*size, dtype: DSPDtype = None) -> DSPTensor:
    dtype = dtype or _float32
    return DSPTensor.create(torch.zeros(*size, dtype=dtype.torch_dtype), dtype)


def ones(*size, dtype: DSPDtype = None) -> DSPTensor:
    dtype = dtype or _float32
    return DSPTensor.create(torch.ones(*size, dtype=dtype.torch_dtype), dtype)


def randn(*size, dtype: DSPDtype = None) -> DSPTensor:
    if _randn_interceptor is not None:
        result = _randn_interceptor(*size, dtype=dtype or _float32)
        if result is not None:
            if result._source is None:
                result._source = "randn"
            return result
    dtype = dtype or _float32
    t = DSPTensor.create(torch.randn(*size, dtype=dtype.torch_dtype), dtype)
    t._source = "randn"
    return t


def zeros_like(t: DSPTensor) -> DSPTensor:
    return DSPTensor.create(torch.zeros_like(t.torch()), t.dsp_dtype)


def ones_like(t: DSPTensor) -> DSPTensor:
    return DSPTensor.create(torch.ones_like(t.torch()), t.dsp_dtype)


def from_torch(t, dtype: DSPDtype) -> DSPTensor:
    return DSPTensor.create(t.to(dtype.torch_dtype), dtype)
