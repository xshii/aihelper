"""算子调用约定 — 基类 + 注册表。

每个 op 在自己的 ops/*.py 里定义 Convention 子类。
dispatch.py 通过 require_convention(op_name) 查找。
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import torch



# ============================================================
# 注册表
# ============================================================

_CONVENTIONS: dict[str, "OpConvention"] = {}


def require_convention(op_name: str) -> "OpConvention":
    conv = _CONVENTIONS.get(op_name)
    if conv is not None:
        return conv
    existing = list(_CONVENTIONS.keys())
    from ..core.errors import ConventionNotFound
    raise ConventionNotFound(
        f"算子 '{op_name}' 无 OpConvention。\n"
        f"已注册的 convention: {existing}\n"
        f"修复: 在对应的 ops/*.py 中定义 Convention 子类。"
    )


# ============================================================
# 基类
# ============================================================

class OpConvention:
    """算子 C 调用约定基类。

    子类通过 op= 参数自动注册:
        class MyConvention(OpConvention, op="my_op"):
            def call_c_func(self, func, *inputs_np, **params): ...
    """
    def __init_subclass__(cls, op: str | list[str] = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if op is not None:
            ops = [op] if isinstance(op, str) else op
            instance = cls()
            for o in ops:
                _CONVENTIONS[o] = instance

    def output_shape(self, *inputs, **op_params) -> tuple:
        """算子的 orig output shape（未 pad）。

        inputs 是原始 torch.Tensor / DSPTensor 位置参数；op_params 是非 tensor kwargs。
        框架用这个结果把 padded result crop 回 orig shape。
        """
        return inputs[0].shape

    def call_c_func(self, func: Callable, *inputs, **params) -> np.ndarray:
        """调 C kernel。

        inputs 的类型由 @register_op 的 raw/fmt 声明决定:
          - 默认（有 fmt 声明）：收到 list[PreparedArg]（见 core/prepare_args.py），
            每个 arg 带 flat / orig_shape / padded_shape / fmt
          - @register_op(raw=True)：收到 raw double ndarray（transpose 这种，框架不
            做任何 pad / flatten / reorder）

        返回 numpy ndarray，形状可以是 padded shape（框架按 orig output shape 自动
        crop 回）。Batch 维语义完全由 Convention 自己处理——框架不切 batch，也不
        stack。op 决定是 for 循环逐片调 kernel 还是一次 bulk 调用（取决于 C 接口）。
        """
        raise NotImplementedError
