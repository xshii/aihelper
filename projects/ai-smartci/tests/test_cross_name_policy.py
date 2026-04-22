"""MergeTriggerRef + CrossNamePolicy 四种策略 + 回归测试

包括 P0 bug 回归：无关 table 不应被跨团队错误合并。
"""
from __future__ import annotations

from smartci.resource_merge.merger import XmlMerger
from smartci.resource_merge.strategies.base import (
    ConflictPolicy,
    CrossNamePolicy,
    MergeStrategy,
    MergeTriggerRef,
    ResourceItem,
)
from smartci.resource_merge.strategies.registry import StrategyRegistry


def _make_cluster_strategy(cross_policy: CrossNamePolicy) -> type:
    class _Cluster(MergeStrategy):
        resource_type = "cluster"
        selector_xpath = "//cluster"
        fields = {"type": "@type"}
        children_xpaths = {"tables": "./ref/@table"}
        key_fields = ["type"]
        conflict_policy = ConflictPolicy.MERGE_CHILDREN
        merge_triggers = [MergeTriggerRef(
            field="tables", target_resource="table",
            target_key_field="name", cross_name_policy=cross_policy,
        )]
    return _Cluster


class _Table(MergeStrategy):
    resource_type = "table"
    selector_xpath = "//table"
    fields = {"name": "@name"}
    key_fields = ["name"]
    conflict_policy = ConflictPolicy.MERGE_CHILDREN


def _make_registry(cluster_cls) -> StrategyRegistry:
    reg = StrategyRegistry()
    reg.register(cluster_cls)
    reg.register(_Table)
    return reg


# ── 构造原始数据 (两团队同 cluster type，各引用不同表名) ──
def _original_data():
    original = {
        "cluster": {
            "team-a": [ResourceItem(
                team="team-a", attrs={"type": "cpu"},
                list_attrs={"tables": ["tbl_a"]},
            )],
            "team-b": [ResourceItem(
                team="team-b", attrs={"type": "cpu"},
                list_attrs={"tables": ["tbl_b"]},
            )],
        },
        "table": {
            "team-a": [ResourceItem(team="team-a", attrs={"name": "tbl_a"})],
            "team-b": [ResourceItem(team="team-b", attrs={"name": "tbl_b"})],
        },
    }
    return original


# ── 四种 cross_name_policy ───────────────────────────
def test_union_as_new_joins_different_names():
    original = _original_data()
    cluster_cls = _make_cluster_strategy(CrossNamePolicy.UNION_AS_NEW)
    registry = _make_registry(cluster_cls)
    merger = XmlMerger(registry=registry)

    merged = {
        "cluster": [ResourceItem(
            team="team-a+team-b", attrs={"type": "cpu"},
            list_attrs={"tables": ["tbl_a", "tbl_b"]}, is_merged=True,
        )],
        "table": [
            ResourceItem(team="team-a", attrs={"name": "tbl_a"}),
            ResourceItem(team="team-b", attrs={"name": "tbl_b"}),
        ],
    }
    merger._apply_merge_triggers(merged, original)

    # UNION_AS_NEW: tbl_a + tbl_b → "tbl_a+tbl_b"
    assert len(merged["table"]) == 1
    assert merged["table"][0].attrs["name"] == "tbl_a+tbl_b"


def test_primary_name_keeps_first_team_name():
    original = _original_data()
    cluster_cls = _make_cluster_strategy(CrossNamePolicy.PRIMARY_NAME)
    registry = _make_registry(cluster_cls)
    merger = XmlMerger(registry=registry)

    merged = {
        "cluster": [ResourceItem(
            team="team-a+team-b", attrs={"type": "cpu"},
            list_attrs={"tables": ["tbl_a", "tbl_b"]}, is_merged=True,
        )],
        "table": [
            ResourceItem(team="team-a", attrs={"name": "tbl_a"}),
            ResourceItem(team="team-b", attrs={"name": "tbl_b"}),
        ],
    }
    merger._apply_merge_triggers(merged, original)

    # PRIMARY_NAME: 取第一个 team（team-a）的第一个名 → tbl_a
    assert len(merged["table"]) == 1
    assert merged["table"][0].attrs["name"] == "tbl_a"


def test_keep_separate_does_not_touch():
    original = _original_data()
    cluster_cls = _make_cluster_strategy(CrossNamePolicy.KEEP_SEPARATE)
    registry = _make_registry(cluster_cls)
    merger = XmlMerger(registry=registry)

    merged = {
        "cluster": [ResourceItem(
            team="team-a+team-b", attrs={"type": "cpu"},
            list_attrs={"tables": ["tbl_a", "tbl_b"]}, is_merged=True,
        )],
        "table": [
            ResourceItem(team="team-a", attrs={"name": "tbl_a"}),
            ResourceItem(team="team-b", attrs={"name": "tbl_b"}),
        ],
    }
    conflicts = merger._apply_merge_triggers(merged, original)
    assert conflicts == []
    # 两张表各自保留
    names = sorted(it.attrs["name"] for it in merged["table"])
    assert names == ["tbl_a", "tbl_b"]


def test_strict_reports_cross_name_conflict():
    original = _original_data()
    cluster_cls = _make_cluster_strategy(CrossNamePolicy.STRICT)
    registry = _make_registry(cluster_cls)
    merger = XmlMerger(registry=registry)

    merged = {
        "cluster": [ResourceItem(
            team="team-a+team-b", attrs={"type": "cpu"},
            list_attrs={"tables": ["tbl_a", "tbl_b"]}, is_merged=True,
        )],
        "table": [
            ResourceItem(team="team-a", attrs={"name": "tbl_a"}),
            ResourceItem(team="team-b", attrs={"name": "tbl_b"}),
        ],
    }
    conflicts = merger._apply_merge_triggers(merged, original)
    assert len(conflicts) == 1
    assert conflicts[0].kind == "cross_name"


def test_strict_passes_when_teams_agree():
    # 两团队引用相同 table 名 → STRICT 不报错
    original = {
        "cluster": {
            "team-a": [ResourceItem(
                team="team-a", attrs={"type": "cpu"},
                list_attrs={"tables": ["shared"]},
            )],
            "team-b": [ResourceItem(
                team="team-b", attrs={"type": "cpu"},
                list_attrs={"tables": ["shared"]},
            )],
        },
        "table": {
            "team-a": [ResourceItem(team="team-a", attrs={"name": "shared"})],
            "team-b": [ResourceItem(team="team-b", attrs={"name": "shared"})],
        },
    }
    cluster_cls = _make_cluster_strategy(CrossNamePolicy.STRICT)
    merger = XmlMerger(registry=_make_registry(cluster_cls))
    merged = {
        "cluster": [ResourceItem(
            team="team-a+team-b", attrs={"type": "cpu"},
            list_attrs={"tables": ["shared"]}, is_merged=True,
        )],
        "table": [
            ResourceItem(team="team-a", attrs={"name": "shared"}),
            ResourceItem(team="team-b", attrs={"name": "shared"}),
        ],
    }
    conflicts = merger._apply_merge_triggers(merged, original)
    assert conflicts == []


# ── P0 回归：无关 table 不应被错误合并 ──────────────
def test_unrelated_table_not_swept_into_cross_merge():
    """回归：team-a 有一张未被 cluster 引用的 tbl_extra，不应被 trigger 合并进 unified。"""
    original = {
        "cluster": {
            "team-a": [ResourceItem(
                team="team-a", attrs={"type": "cpu"},
                list_attrs={"tables": ["tbl_a"]},
            )],
            "team-b": [ResourceItem(
                team="team-b", attrs={"type": "cpu"},
                list_attrs={"tables": ["tbl_b"]},
            )],
        },
        "table": {
            "team-a": [
                ResourceItem(team="team-a", attrs={"name": "tbl_a"}),
                ResourceItem(team="team-a", attrs={"name": "tbl_extra"}),  # 未被引用
            ],
            "team-b": [ResourceItem(team="team-b", attrs={"name": "tbl_b"})],
        },
    }
    cluster_cls = _make_cluster_strategy(CrossNamePolicy.UNION_AS_NEW)
    merger = XmlMerger(registry=_make_registry(cluster_cls))
    merged = {
        "cluster": [ResourceItem(
            team="team-a+team-b", attrs={"type": "cpu"},
            list_attrs={"tables": ["tbl_a", "tbl_b"]}, is_merged=True,
        )],
        "table": [
            ResourceItem(team="team-a", attrs={"name": "tbl_a"}),
            ResourceItem(team="team-a", attrs={"name": "tbl_extra"}),
            ResourceItem(team="team-b", attrs={"name": "tbl_b"}),
        ],
    }
    merger._apply_merge_triggers(merged, original)

    names = sorted(it.attrs["name"] for it in merged["table"])
    # tbl_a + tbl_b → "tbl_a+tbl_b"；tbl_extra 原样保留
    assert "tbl_extra" in names
    assert "tbl_a+tbl_b" in names
    assert len(names) == 2


def test_no_trigger_when_no_merge_happened():
    """单一团队场景：cluster 没融合，不应触发 trigger。"""
    original = {
        "cluster": {
            "team-a": [ResourceItem(
                team="team-a", attrs={"type": "cpu"},
                list_attrs={"tables": ["tbl_a"]},
            )],
        },
        "table": {
            "team-a": [ResourceItem(team="team-a", attrs={"name": "tbl_a"})],
        },
    }
    cluster_cls = _make_cluster_strategy(CrossNamePolicy.UNION_AS_NEW)
    merger = XmlMerger(registry=_make_registry(cluster_cls))
    merged = {
        "cluster": [ResourceItem(
            team="team-a", attrs={"type": "cpu"},
            list_attrs={"tables": ["tbl_a"]}, is_merged=False,  # ← 未融合
        )],
        "table": [ResourceItem(team="team-a", attrs={"name": "tbl_a"})],
    }
    conflicts = merger._apply_merge_triggers(merged, original)
    assert conflicts == []
    # table 不被重命名（unified_name 不应该被生成）
    assert merged["table"][0].attrs["name"] == "tbl_a"
