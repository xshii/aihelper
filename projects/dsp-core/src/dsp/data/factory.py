"""工厂函数 — 创建 DSPTensor（形似 torch.xxx）。

所有工厂函数返回的 DSPTensor 都用 torch.double 存储；
dsp_dtype 只是语义标签，硬件量化通过 pre_quantize / fake_quantize 实现。

用法:
    import dsp
    a = dsp.data.randn(4, 8, dtype=dsp.core.bf16)
    b = dsp.data.zeros(10, dtype=dsp.core.bf16)
"""

from __future__ import annotations

import torch

from ..core.tensor import DSPTensor
from ..core.dtype import DSPDtype
from ..core.enums import TensorSource
from ..core import double as _double


# 依赖注入：context 启动时注入 randn 拦截器
_randn_interceptor = None


def set_randn_interceptor(interceptor):
    """由 context 模块注入。data 不直接 import context。"""
    global _randn_interceptor
    _randn_interceptor = interceptor


def tensor(data, dtype: DSPDtype = None, requires_grad: bool = False) -> DSPTensor:
    dtype = dtype or _double
    # 内存全程 double 存储，dsp_dtype 只作标签
    return DSPTensor.create(
        torch.tensor(data, dtype=torch.double, requires_grad=requires_grad), dtype)


def zeros(*size, dtype: DSPDtype = None) -> DSPTensor:
    dtype = dtype or _double
    return DSPTensor.create(torch.zeros(*size, dtype=torch.double), dtype)


def ones(*size, dtype: DSPDtype = None) -> DSPTensor:
    dtype = dtype or _double
    return DSPTensor.create(torch.ones(*size, dtype=torch.double), dtype)


def randn(*size, dtype: DSPDtype = None) -> DSPTensor:
    if _randn_interceptor is not None:
        result = _randn_interceptor(*size, dtype=dtype or _double)
        if result is not None:
            if result._source is None:
                result._source = TensorSource.RANDN
            return result
    dtype = dtype or _double
    # 内存全程 double 存储；dsp_dtype 只是标签，pre_quantize 会按需量化
    t = torch.randn(*size, dtype=torch.double)
    result = DSPTensor.create(t, dtype)
    result._source = TensorSource.RANDN
    return result


def zeros_like(t: DSPTensor) -> DSPTensor:
    return DSPTensor.create(torch.zeros_like(t.torch()), t.dsp_dtype)


def ones_like(t: DSPTensor) -> DSPTensor:
    return DSPTensor.create(torch.ones_like(t.torch()), t.dsp_dtype)


def from_torch(t, dtype: DSPDtype) -> DSPTensor:
    """把任意 torch.Tensor 包成 DSPTensor，统一转 double 存储 + 打 dsp_dtype 标签。"""
    return DSPTensor.create(t.double(), dtype)
