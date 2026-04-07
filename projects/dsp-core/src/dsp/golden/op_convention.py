"""算子调用约定：每种 op 声明自己的 C 函数调用方式。

两个方法:
    output_shape(*inputs)            — 从输入 tensor 推算输出 shape
    call_c_func(func, *inputs_np, **params) — 调 C 函数

新增 op 用 __init_subclass__ 自动注册:
    class FFTConvention(OpConvention, op="fft"):
        def output_shape(self, *inputs): ...
        def call_c_func(self, func, *inputs_np, **params): ...
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np
import torch


# ============================================================
# 注册表
# ============================================================

_CONVENTIONS: dict[str, OpConvention] = {}


def get_convention(op_name: str) -> Optional[OpConvention]:
    return _CONVENTIONS.get(op_name)


def register_convention(op_name: str, conv: OpConvention):
    _CONVENTIONS[op_name] = conv


# ============================================================
# 基类
# ============================================================

class OpConvention:
    """一种 op 的 C 函数调用约定。

    子类用 __init_subclass__ 自动注册:
        class LinearConvention(OpConvention, op="linear"):
            def output_shape(self, x, weight, bias): ...
            def call_c_func(self, func, x_np, weight_np, bias_np=None, scale_exp=0): ...
    """

    def __init_subclass__(cls, op: str | list[str] = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if op is not None:
            ops = [op] if isinstance(op, str) else op
            instance = cls()
            for o in ops:
                _CONVENTIONS[o] = instance

    def output_shape(self, *inputs: torch.Tensor) -> tuple:
        """从输入 tensor 推算输出 shape。"""
        return inputs[0].shape

    def call_c_func(self, func: Callable, *inputs_np: np.ndarray, **params) -> np.ndarray:
        """调 C 函数。inputs_np 按顺序对应 ComputeKey 的 in0, in1, in2。

        params 包含非 tensor 参数（scale_exp 等）。
        """
        raise NotImplementedError


# ============================================================
# 内置 Convention（定义即注册）
# ============================================================

class UnaryConvention(OpConvention, op="abs"):
    """一元算子: func(input, output, count)"""

    def call_c_func(self, func, *inputs_np, **params):
        x = inputs_np[0].flatten()
        out = np.zeros_like(x)
        func(x, out, x.size)
        return out


class ElementwiseConvention(OpConvention, op=["add", "mul", "sub"]):
    """二元逐元素: func(a, b, output, count)"""

    def call_c_func(self, func, *inputs_np, **params):
        a = inputs_np[0].flatten()
        b = inputs_np[1].flatten()
        count = min(a.size, b.size)
        out = np.zeros(count, dtype=np.float32)
        func(a[:count], b[:count], out, count)
        return out


class MatmulConvention(OpConvention, op="matmul"):
    """矩阵乘: func(A, B, C, M, K, N)"""

    def output_shape(self, *inputs):
        a, b = inputs[0], inputs[1]
        return (*a.shape[:-1], b.shape[-1])

    def call_c_func(self, func, *inputs_np, **params):
        a, b = inputs_np[0], inputs_np[1]
        if a.ndim < 2:
            a = a.reshape(1, -1)
        if b.ndim < 2:
            b = b.reshape(-1, 1)
        M, K = a.shape[-2], a.shape[-1]
        N = b.shape[-1]
        out = np.zeros(M * N, dtype=np.float32)
        func(a.flatten(), b.flatten(), out, M, K, N)
        return out.reshape(M, N)


class LinearConvention(OpConvention, op="linear"):
    """Fused matmul+bias+scale: func(input, weight, bias, output, scale_exp, M, K, N)"""

    def output_shape(self, *inputs):
        x, weight = inputs[0], inputs[1]
        return (*x.shape[:-1], weight.shape[-1])

    def call_c_func(self, func, *inputs_np, **params):
        x, weight = inputs_np[0], inputs_np[1]
        bias = inputs_np[2] if len(inputs_np) > 2 else None
        scale_exp = params.get("scale_exp", 0)

        if x.ndim < 2:
            x = x.reshape(1, -1)
        if weight.ndim < 2:
            weight = weight.reshape(-1, 1)
        M, K = x.shape[-2], x.shape[-1]
        N = weight.shape[-1]
        out = np.zeros(M * N, dtype=np.float32)

        if bias is not None:
            func(x.flatten(), weight.flatten(), bias.flatten(), out, scale_exp, M, K, N)
        else:
            func(x.flatten(), weight.flatten(), out, scale_exp, M, K, N)
        return out.reshape(M, N)


class CorrelateConvention(OpConvention, op="correlate"):
    """互相关: func(signal, template, output, signal_len)"""

    def output_shape(self, *inputs):
        a, b = inputs[0], inputs[1]
        n = a.shape[-1] + b.shape[-1] - 1
        return (*a.shape[:-1], n)

    def call_c_func(self, func, *inputs_np, **params):
        a, b = inputs_np[0], inputs_np[1]
        n_out = a.shape[-1] + b.shape[-1] - 1
        out = np.zeros(n_out, dtype=np.float32)
        func(a.flatten(), b.flatten(), out, a.shape[-1])
        return out
