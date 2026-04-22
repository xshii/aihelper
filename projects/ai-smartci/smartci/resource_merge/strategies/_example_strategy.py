"""示例合并策略 - 最小子类（无 children、无 trigger）

展示最小写法：5 个 ClassVar。不覆盖任何钩子即获得"按 key 去重、冲突报错"。

>>> from smartci.resource_merge.strategies._example_strategy import ExampleStrategy
>>> ExampleStrategy.resource_type
'_example'
>>> ExampleStrategy.key_fields
['id']
"""

from __future__ import annotations
from smartci.resource_merge.strategies.base import ConflictPolicy, MergeStrategy
from smartci.resource_merge.strategies.registry import StrategyRegistry


@StrategyRegistry.default().register
class ExampleStrategy(MergeStrategy):
    resource_type = "_example"
    selector_xpath = "//example"
    fields = {"id": "@id", "value": "@value"}
    key_fields = ["id"]
    conflict_policy = ConflictPolicy.ERROR
