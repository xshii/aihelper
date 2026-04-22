"""PackagerRegistry - 平台打包器注册表

PATTERN: 与 resource_merge.strategies.StrategyRegistry 同构——实例级表 + default() 单例。
         装饰器 @register_packager 作简写，等价 PackagerRegistry.default().register。
"""

from __future__ import annotations
from typing import Dict, List, Type

from smartci.packaging.packager.base import PlatformPackager


class PackagerRegistry:
    _default: "PackagerRegistry" = None  # type: ignore[assignment]

    def __init__(self) -> None:
        self._table: Dict[str, Type[PlatformPackager]] = {}

    @classmethod
    def default(cls) -> "PackagerRegistry":
        if cls._default is None:
            cls._default = cls()
        return cls._default

    def register(self, packager_cls: Type[PlatformPackager]) -> Type[PlatformPackager]:
        platform = packager_cls.platform
        if not platform:
            raise ValueError(f"{packager_cls.__name__}.platform 未声明")
        if platform in self._table:
            prev = self._table[platform]
            raise ValueError(
                f"platform={platform!r} 已被 {prev.__name__} 注册，"
                f"新来者 {packager_cls.__name__} 冲突"
            )
        self._table[platform] = packager_cls
        return packager_cls

    def get(self, platform: str) -> Type[PlatformPackager]:
        if platform not in self._table:
            raise KeyError(
                f"未注册的 platform: {platform!r}（已注册: {sorted(self._table)}）"
            )
        return self._table[platform]

    def list_platforms(self) -> List[str]:
        return sorted(self._table)


def register_packager(cls: Type[PlatformPackager]) -> Type[PlatformPackager]:
    """装饰器简写。等价 PackagerRegistry.default().register。"""
    return PackagerRegistry.default().register(cls)
