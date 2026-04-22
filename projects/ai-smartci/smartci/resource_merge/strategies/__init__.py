"""合并策略插件层

加新资源类型：在此目录下写 `{resource_type}_strategy.py`，
用 `@StrategyRegistry.default().register` 注册。参考 `_example_strategy.py` +
`_cluster_example.py`。
"""

from __future__ import annotations
# 触发内置示例 strategy 的注册（副作用 import）
from smartci.resource_merge.strategies import _example_strategy  # noqa: F401
from smartci.resource_merge.strategies import _cluster_example   # noqa: F401
