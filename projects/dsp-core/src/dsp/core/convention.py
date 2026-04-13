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

    def output_shape(self, *inputs: torch.Tensor) -> tuple:
        return inputs[0].shape

    def call_c_func(self, func: Callable, *inputs_np: np.ndarray, **params) -> np.ndarray:
        raise NotImplementedError
