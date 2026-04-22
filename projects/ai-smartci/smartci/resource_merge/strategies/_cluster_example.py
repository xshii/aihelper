"""Cluster + Table 示例 — 展示三层 XML 建模 + 跨表触发合并

对应 XML 结构:
    <cluster type="cpu_cluster" number="2">
      <ref table="tbl_irq"/>
      <ref table="tbl_mem"/>
    </cluster>

    <table name="tbl_irq" count="5">
      <irq id="1" handler="h1"/>
      ...
    </table>

要点:
  - ClusterStrategy.conflict_policy = MERGE_CHILDREN  → 同 type 的 cluster 融合 tables 并集
  - count_field="number" → 融合后 number 属性不写回（由运行时重算）
  - merge_triggers: 融合时触发 table 的跨团队合并，cross_name_policy=UNION_AS_NEW
    让不同表名的 table 也能并成一张
  - TableStrategy.conflict_policy = MERGE_CHILDREN → 同名 table 合并 rows
  - TableStrategy.count_field="count" → 跟 cluster 不同名（按用户需求各自配置）
"""

from __future__ import annotations
from smartci.resource_merge.strategies.base import (
    ConflictPolicy,
    CrossNamePolicy,
    MergeStrategy,
    MergeTriggerRef,
)
from smartci.resource_merge.strategies.registry import StrategyRegistry


@StrategyRegistry.default().register
class ClusterStrategy(MergeStrategy):
    resource_type    = "cluster"
    selector_xpath   = "//cluster"
    fields           = {"type": "@type", "number": "@number"}
    children_xpaths  = {"tables": "./ref/@table"}
    key_fields       = ["type"]
    count_field      = "number"
    conflict_policy  = ConflictPolicy.MERGE_CHILDREN
    merge_triggers   = [MergeTriggerRef(
        field="tables",
        target_resource="table",
        target_key_field="name",
        cross_name_policy=CrossNamePolicy.UNION_AS_NEW,
    )]


@StrategyRegistry.default().register
class TableStrategy(MergeStrategy):
    resource_type    = "table"
    selector_xpath   = "//table"
    fields           = {"name": "@name", "count": "@count"}
    children_xpaths  = {"rows": "./*/@id"}     # 简化：只抽子元素 id 作为 list
    key_fields       = ["name"]
    count_field      = "count"                  # 注意：跟 cluster 不同名
    conflict_policy  = ConflictPolicy.MERGE_CHILDREN
