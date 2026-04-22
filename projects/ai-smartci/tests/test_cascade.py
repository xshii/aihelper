"""XmlMerger 级联传播与环检测测试

验证:
  - _apply_fk: team 作用域内的 value remap 正确应用
  - _apply_cascade 单轮：team 错匹配时不应用
  - CascadeCycleError: 当前 stub 逻辑下 new_remaps 始终空（环检测占位）
"""

from __future__ import annotations
import pytest

from smartci.resource_merge.merger import XmlMerger
from smartci.resource_merge.strategies.base import (
    ConflictPolicy,
    ForeignKeyRef,
    MergeStrategy,
    ResourceItem,
    ValueRemap,
)
from smartci.resource_merge.strategies.registry import StrategyRegistry


class _Irq(MergeStrategy):
    resource_type = "irq"
    selector_xpath = "//irq"
    fields = {"irq_id": "@irq_id"}
    key_fields = ["irq_id"]
    conflict_policy = ConflictPolicy.RENAME_ON_CONFLICT


class _Cpu(MergeStrategy):
    resource_type = "cpu"
    selector_xpath = "//cpu"
    fields = {"cpu_id": "@cpu_id", "irq_ref": "@irq_ref"}
    key_fields = ["cpu_id"]
    conflict_policy = ConflictPolicy.ERROR
    foreign_keys = [ForeignKeyRef("irq_ref", "irq", "irq_id")]


@pytest.fixture
def isolated_registry():
    """用独立 registry 避免污染全局 default。"""
    reg = StrategyRegistry()
    reg.register(_Irq)
    reg.register(_Cpu)
    return reg


def test_cascade_applies_per_team(isolated_registry):
    merged_by_type = {
        "cpu": [
            ResourceItem(team="team-a", attrs={"cpu_id": "cpu0", "irq_ref": "1"}),
            ResourceItem(team="team-b", attrs={"cpu_id": "cpu1", "irq_ref": "1"}),
        ],
    }
    remaps = [ValueRemap(
        team="team-b", resource_type="irq", field="irq_id",
        old_value="1", new_value="team-b_1",
    )]
    merger = XmlMerger(registry=isolated_registry)
    applied = merger._apply_cascade(merged_by_type, remaps)
    assert applied == 1
    # team-a.cpu0.irq_ref 不变
    assert merged_by_type["cpu"][0].attrs["irq_ref"] == "1"
    # team-b.cpu1.irq_ref 跟随 rename
    assert merged_by_type["cpu"][1].attrs["irq_ref"] == "team-b_1"


def test_cascade_noop_when_team_mismatches(isolated_registry):
    """remap.team=team-b 不应改 team-a 的引用"""
    merged_by_type = {
        "cpu": [
            ResourceItem(team="team-a", attrs={"cpu_id": "cpu0", "irq_ref": "1"}),
        ],
    }
    remaps = [ValueRemap(
        team="team-b", resource_type="irq", field="irq_id",
        old_value="1", new_value="team-b_1",
    )]
    merger = XmlMerger(registry=isolated_registry)
    applied = merger._apply_cascade(merged_by_type, remaps)
    assert applied == 0
    assert merged_by_type["cpu"][0].attrs["irq_ref"] == "1"


def test_foreign_key_validation_detects_dangling_ref(isolated_registry):
    """cpu.irq_ref 指向不存在的 irq_id → foreign_key conflict"""
    merged_by_type = {
        "irq": [ResourceItem(team="team-a", attrs={"irq_id": "1"})],
        "cpu": [
            ResourceItem(team="team-a", attrs={"cpu_id": "cpu0", "irq_ref": "999"}),
        ],
    }
    merger = XmlMerger(registry=isolated_registry)
    conflicts = merger._check_foreign_keys(merged_by_type)
    assert len(conflicts) == 1
    assert conflicts[0].kind == "foreign_key"
    assert "999" in conflicts[0].detail
