"""数据生成策略 — 非算子感知。

定义验证时使用的各种数据分布：全随机、稀疏、精确值、边界等。
纯函数，不依赖任何全局状态、不感知算子。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch


@dataclass(slots=True, frozen=True)
class DataStrategy:
    """一种数据生成策略。frozen=True 防意外修改，slots=True 拼错属性立即报错。"""
    name: str
    sparsity: float = 0.0
    precision_exact: bool = False
    value_range: Optional[tuple] = None

    def __str__(self):
        if self.precision_exact:
            return f"{self.name}(precision_exact)"
        if self.sparsity > 0:
            return f"{self.name}(sparsity={self.sparsity})"
        return self.name


DEFAULT_STRATEGIES = [
    DataStrategy("math"),  # 数学验证：由各 op 的 math_strategy 构造已知解
    DataStrategy("precision_exact", precision_exact=True, value_range=(-100, 100)),
    DataStrategy("random"),
    DataStrategy("sparse_30", sparsity=0.3),
    DataStrategy("sparse_50", sparsity=0.5),
    DataStrategy("sparse_90", sparsity=0.9),
    DataStrategy("sparse_9999", sparsity=0.9999),
    DataStrategy("corner_all_zero", sparsity=1.0),
]

# use_input 时的运行模式顺序
from ..core.enums import Mode
USE_INPUT_MODES = [Mode.TORCH, Mode.PSEUDO_QUANT, Mode.GOLDEN_C]


def generate_by_strategy(
    *size,
    dtype_torch: torch.dtype,
    strategy: DataStrategy,
) -> torch.Tensor:
    """按策略生成数据。纯函数，不依赖任何全局状态。"""
    if strategy.precision_exact:
        lo, hi = strategy.value_range or (-100, 100)
        int_vals = torch.randint(lo, hi + 1, size)
        return int_vals.to(dtype_torch)

    if strategy.sparsity >= 1.0:
        return torch.zeros(*size, dtype=dtype_torch)

    t = torch.randn(*size, dtype=dtype_torch)
    if strategy.sparsity > 0:
        mask = torch.rand(*size) < strategy.sparsity
        if t.is_complex():
            t[mask] = 0 + 0j
        else:
            t[mask] = 0.0
    return t
