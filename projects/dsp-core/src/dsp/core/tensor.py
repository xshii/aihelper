"""DSPTensor: torch.Tensor 子类 + 自定义 dtype 元数据。

核心设计: DSPTensor IS-A torch.Tensor。
所有 torch 方法天然可用（.shape, .to(), 索引, .cuda(), torch.save 等），零额外代码。
__torch_function__ 只做一件事: 操作后传播 native_type 元数据到结果。

用法:
    a = DSPTensor.create(torch.randn(100, dtype=torch.int16), dsp.int16)
    b = a + a          # 返回 DSPTensor, dtype=dsp.int16
    c = torch.abs(a)   # 返回 DSPTensor, dtype 自动推断
    t = a.torch()      # 脱壳为标准 torch.Tensor
"""

from __future__ import annotations

from typing import Optional

import torch

from .dtype import DSPDtype


class DSPTensor(torch.Tensor):
    """torch.Tensor 子类，附加 DSPDtype 元数据。

    底层数据存储在标准 torch dtype (float32/int16/...) 中。
    _dsp_dtype 属性记录原生类型（int16/int8/...）。
    """

    # 标记: 告诉 torch 这是一个 Tensor 子类
    _dsp_dtype: Optional[DSPDtype] = None
    _source: Optional[str] = None  # "randn" | "op_output" | None

    # ------------------------------------------------------------------
    # 创建
    # ------------------------------------------------------------------

    @staticmethod
    def create(data: torch.Tensor, dsp_dtype: DSPDtype) -> DSPTensor:
        """从标准 torch.Tensor + DSPDtype 创建 DSPTensor。

        这是推荐的创建方式。data 应已经在 float 域中。
        """
        t = data.as_subclass(DSPTensor)
        t._dsp_dtype = dsp_dtype
        return t

    # ------------------------------------------------------------------
    # __torch_function__: 拦截 torch 操作，传播元数据
    # ------------------------------------------------------------------

    @classmethod
    def __torch_function__(cls, func, types, args=(), kwargs=None):
        """所有 torch 操作经过这里。

        策略:
        1. 让 torch 正常执行操作
        2. 如果结果是 Tensor，附上从输入推断的 _dsp_dtype
        3. 非 Tensor 结果（如 .shape, .item()）直接返回
        """
        kwargs = kwargs or {}

        # 执行原始 torch 操作
        result = super().__torch_function__(func, types, args, kwargs)

        # 从输入推断 dsp_dtype
        dsp_dtype = _infer_dtype_from_args(args)

        # 给结果附上元数据
        if isinstance(result, torch.Tensor) and not isinstance(result, DSPTensor):
            if dsp_dtype is not None:
                result = result.as_subclass(DSPTensor)
                result._dsp_dtype = dsp_dtype
        elif isinstance(result, DSPTensor) and result._dsp_dtype is None:
            result._dsp_dtype = dsp_dtype

        # 处理返回 tuple 的情况 (如 torch.max 返回 values + indices)
        if isinstance(result, tuple):
            result = tuple(
                _attach_dtype(r, dsp_dtype) if isinstance(r, torch.Tensor) else r
                for r in result
            )

        return result

    # ------------------------------------------------------------------
    # 自定义属性
    # ------------------------------------------------------------------

    @property
    def dsp_dtype(self) -> Optional[DSPDtype]:
        """获取 DSP 数据类型。"""
        return self._dsp_dtype

    # 覆盖 dtype 属性: 打印时显示 dsp.int16 而非 torch.int16
    # 注意: 不覆盖真正的 torch dtype，因为 torch 内部需要它
    # 用 .dsp_dtype 获取 DSP 类型，用 .torch_dtype 获取 torch 类型

    @property
    def torch_dtype(self) -> torch.dtype:
        """底层 torch 存储类型。"""
        # 调用父类的 dtype
        return super().dtype

    # ------------------------------------------------------------------
    # 显式转换
    # ------------------------------------------------------------------

    def torch(self) -> torch.Tensor:
        """脱壳为标准 torch.Tensor (丢弃 DSP 元数据)。"""
        return self.as_subclass(torch.Tensor)

    def to_dsp(self, target_dtype: DSPDtype) -> DSPTensor:
        """DSP 类型转换: dsp.int16 → dsp.int32 等。

        底层 torch dtype 也会相应改变。
        """
        data = self.to(target_dtype.torch_dtype)
        return DSPTensor.create(data, target_dtype)

    def native_bytes(self) -> torch.Tensor:
        """转换为原生格式 tensor (给 C++ / 硬件消费)。"""
        from .codec import get_codec
        codec = get_codec(self._dsp_dtype)
        return codec.from_float(self, self._dsp_dtype)

    def fake_quantize(self) -> DSPTensor:
        """伪量化: 截断到原生精度但保持 float。"""
        from .codec import get_codec
        codec = get_codec(self._dsp_dtype)
        result = codec.fake_quantize(self, self._dsp_dtype)
        return DSPTensor.create(result, self._dsp_dtype)

    # ------------------------------------------------------------------
    # 显示
    # ------------------------------------------------------------------

    def __repr__(self):
        data_str = self.torch().__repr__()
        if self._dsp_dtype is not None:
            # 把 "tensor(" 替换成 "dsp.tensor("，末尾加 dtype
            inner = data_str.replace("tensor(", "", 1)
            if inner.endswith(")"):
                inner = inner[:-1]
            return f"dsp.tensor({inner}, dsp_dtype={self._dsp_dtype})"
        return data_str


# ============================================================
# 辅助函数
# ============================================================

def _infer_dtype_from_args(args) -> Optional[DSPDtype]:
    """从操作的参数中推断 DSPDtype。"""
    for arg in _flatten_args(args):
        if isinstance(arg, DSPTensor) and arg._dsp_dtype is not None:
            return arg._dsp_dtype
    return None


def _flatten_args(args):
    """展开嵌套的参数列表。"""
    for arg in args:
        if isinstance(arg, (list, tuple)):
            yield from _flatten_args(arg)
        else:
            yield arg


def _attach_dtype(t: torch.Tensor, dsp_dtype: Optional[DSPDtype]) -> torch.Tensor:
    """给 Tensor 附上 DSPDtype（如果有的话）。"""
    if dsp_dtype is not None and not isinstance(t, DSPTensor):
        t = t.as_subclass(DSPTensor)
        t._dsp_dtype = dsp_dtype
    return t
