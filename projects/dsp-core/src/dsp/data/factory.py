"""工厂函数 — 创建 DSPTensor（形似 torch.xxx）。

用法:
    import dsp
    a = dsp.data.randn(4, 8, dtype=dsp.core.bint16)
    b = dsp.data.zeros(10, dtype=dsp.core.float32)
"""

from __future__ import annotations

import torch

from ..core.tensor import DSPTensor
from ..core.dtype import DSPDtype
from ..core import double as _double


# 依赖注入：context 启动时注入 randn 拦截器
_randn_interceptor = None


def set_randn_interceptor(interceptor):
    """由 context 模块注入。data 不直接 import context。"""
    global _randn_interceptor
    _randn_interceptor = interceptor


def _to_int_dtype(data: torch.Tensor, dtype: DSPDtype) -> torch.Tensor:
    """将 float tensor 转为 int dtype: round + clamp + cast。"""
    torch_dt = dtype.torch_dtype
    if torch_dt == torch.int8:
        return data.round().clamp(-128, 127).to(torch_dt)
    elif torch_dt == torch.int16:
        return data.round().clamp(-32768, 32767).to(torch_dt)
    elif torch_dt == torch.int32:
        return data.round().clamp(-(1 << 31), (1 << 31) - 1).to(torch_dt)
    return data.to(torch_dt)


def tensor(data, dtype: DSPDtype = None, requires_grad: bool = False) -> DSPTensor:
    dtype = dtype or _double
    return DSPTensor.create(
        torch.tensor(data, dtype=dtype.torch_dtype, requires_grad=requires_grad), dtype)


def zeros(*size, dtype: DSPDtype = None) -> DSPTensor:
    dtype = dtype or _double
    return DSPTensor.create(torch.zeros(*size, dtype=dtype.torch_dtype), dtype)


def ones(*size, dtype: DSPDtype = None) -> DSPTensor:
    dtype = dtype or _double
    return DSPTensor.create(torch.ones(*size, dtype=dtype.torch_dtype), dtype)


def randn(*size, dtype: DSPDtype = None) -> DSPTensor:
    if _randn_interceptor is not None:
        result = _randn_interceptor(*size, dtype=dtype or _double)
        if result is not None:
            if result._source is None:
                result._source = "randn"
            return result
    dtype = dtype or _double
    torch_dt = dtype.torch_dtype
    if not torch_dt.is_floating_point:
        # int 类型: 先生成 float，再 round+clamp+cast
        t_float = torch.randn(*size, dtype=torch.float32)
        t = _to_int_dtype(t_float, dtype)
    else:
        t = torch.randn(*size, dtype=torch_dt)
    result = DSPTensor.create(t, dtype)
    result._source = "randn"
    return result


def zeros_like(t: DSPTensor) -> DSPTensor:
    return DSPTensor.create(torch.zeros_like(t.torch()), t.dsp_dtype)


def ones_like(t: DSPTensor) -> DSPTensor:
    return DSPTensor.create(torch.ones_like(t.torch()), t.dsp_dtype)


def from_torch(t, dtype: DSPDtype) -> DSPTensor:
    return DSPTensor.create(t.to(dtype.torch_dtype), dtype)
