"""StrategyRegistry - 按 resource_type 管理 MergeStrategy 子类

PATTERN: classmethod 注册表 + singleton-like default() 入口；支持多实例（便于测试隔离）。
"""

from __future__ import annotations
from typing import Dict, List, Type

from smartci.resource_merge.strategies.base import MergeStrategy


class StrategyRegistry:
    """实例级注册表。默认用 `StrategyRegistry.default()` 拿全局单例。"""

    _default: "StrategyRegistry" = None  # type: ignore[assignment]

    def __init__(self) -> None:
        self._table: Dict[str, Type[MergeStrategy]] = {}

    @classmethod
    def default(cls) -> "StrategyRegistry":
        if cls._default is None:
            cls._default = cls()
        return cls._default

    def register(self, strategy_cls: Type[MergeStrategy]) -> Type[MergeStrategy]:
        """作装饰器用。校验 resource_type 非空 + 不重复。"""
        rt = strategy_cls.resource_type
        if not rt:
            raise ValueError(f"{strategy_cls.__name__}.resource_type 未设置")
        if rt in self._table:
            prev = self._table[rt]
            raise ValueError(
                f"resource_type={rt!r} 已被 {prev.__name__} 注册，"
                f"新来者 {strategy_cls.__name__} 冲突"
            )
        self._table[rt] = strategy_cls
        return strategy_cls

    def get(self, resource_type: str) -> Type[MergeStrategy]:
        if resource_type not in self._table:
            raise KeyError(
                f"未注册的 resource_type: {resource_type!r}（已注册: {sorted(self._table)}）"
            )
        return self._table[resource_type]

    def list_types(self) -> List[str]:
        return sorted(self._table)
