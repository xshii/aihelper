"""MergeStrategy 核心行为测试

覆盖:
  - ERROR 策略：冲突记 conflict，不 rename
  - RENAME_ON_CONFLICT：后来者 rename + 生成 ValueRemap（单 team 作用域）
  - validate_item：ValueError → kind="validate" 冲突
  - is_conflict 覆盖：同 key 字段一致时不算冲突
  - resolve 覆盖：自定义合并（字段拼接）
"""

from __future__ import annotations
from smartci.resource_merge.strategies.base import (
    ConflictPolicy,
    ForeignKeyRef,
    MergeStrategy,
    ResourceItem,
    ValueRemap,
)


class _ErrorIrq(MergeStrategy):
    resource_type = "irq"
    selector_xpath = "//irq"
    fields = {"irq_id": "@irq_id", "handler": "@handler"}
    key_fields = ["irq_id"]
    conflict_policy = ConflictPolicy.ERROR


class _RenameIrq(MergeStrategy):
    resource_type = "irq"
    selector_xpath = "//irq"
    fields = {"irq_id": "@irq_id", "handler": "@handler"}
    key_fields = ["irq_id"]
    conflict_policy = ConflictPolicy.RENAME_ON_CONFLICT


class _OffsetIrq(_RenameIrq):
    """覆盖 rename_key_value: 数字 id + 团队 offset。"""

    def rename_key_value(self, team: str, field_name: str, old_value: str) -> str:
        offsets = {"team-a": 0, "team-b": 1000}
        return str(int(old_value) + offsets[team])


class _JoinHandlers(_RenameIrq):
    """覆盖 is_conflict + resolve：同 key 字段差异时用 "," 拼接 handler。"""

    conflict_policy = ConflictPolicy.ERROR  # 不走 rename

    def is_conflict(self, a, b):
        return a.attrs != b.attrs

    def resolve(self, a, b):
        return ResourceItem(
            team=f"{a.team}+{b.team}",
            attrs={
                "irq_id": a.attrs["irq_id"],
                "handler": f"{a.attrs['handler']},{b.attrs['handler']}",
            },
        )


# ── 测试 ───────────────────────────────────────────────
def test_error_policy_records_conflict(sample_items_by_team):
    result = _ErrorIrq().merge(sample_items_by_team)
    # 先到先得：team-a 的 irq_id=1 保留，team-b 的 irq_id=1 记 conflict
    assert {it.attrs["irq_id"] for it in result.merged} == {"1", "2", "3"}
    assert len(result.conflicts) == 1
    assert result.conflicts[0].kind == "conflict"
    assert result.conflicts[0].teams == ["team-a", "team-b"]
    assert result.remaps == []


def test_rename_policy_produces_value_remap(sample_items_by_team):
    result = _RenameIrq().merge(sample_items_by_team)
    ids = sorted(it.attrs["irq_id"] for it in result.merged)
    # team-b 的 irq_id=1 被 rename 成 team-b_1
    assert ids == ["1", "2", "3", "team-b_1"]
    assert len(result.remaps) == 1
    r = result.remaps[0]
    assert r == ValueRemap(
        team="team-b", resource_type="irq", field="irq_id",
        old_value="1", new_value="team-b_1",
    )
    assert result.conflicts == []  # rename 后不再冲突


def test_rename_key_value_override_numeric_offset(sample_items_by_team):
    result = _OffsetIrq().merge(sample_items_by_team)
    ids = sorted(it.attrs["irq_id"] for it in result.merged)
    # 原始 1/2/3；team-b 的 1 → 1001（按 offset 钩子）
    assert ids == ["1", "1001", "2", "3"]
    assert result.remaps[0].new_value == "1001"


def test_validate_item_failure_becomes_conflict():
    class _Validated(_ErrorIrq):
        def validate_item(self, item):
            if not item.attrs.get("handler"):
                raise ValueError("handler 必填")

    items = {
        "team-a": [ResourceItem(team="team-a", attrs={"irq_id": "1", "handler": ""})],
    }
    result = _Validated().merge(items)
    assert result.merged == []
    assert len(result.conflicts) == 1
    assert result.conflicts[0].kind == "validate"


def test_resolve_override_joins_fields():
    items = {
        "team-a": [ResourceItem(team="team-a", attrs={"irq_id": "1", "handler": "a"})],
        "team-b": [ResourceItem(team="team-b", attrs={"irq_id": "1", "handler": "b"})],
    }
    result = _JoinHandlers().merge(items)
    assert len(result.merged) == 1
    assert result.merged[0].attrs["handler"] == "a,b"
    assert result.merged[0].team == "team-a+team-b"


def test_foreign_keys_declaration_available():
    class _Cpu(MergeStrategy):
        resource_type = "cpu"
        selector_xpath = "//cpu"
        fields = {"cpu_id": "@cpu_id", "irq_ref": "@irq_ref"}
        key_fields = ["cpu_id"]
        conflict_policy = ConflictPolicy.ERROR
        foreign_keys = [ForeignKeyRef("irq_ref", "irq", "irq_id")]

    # 只验证声明能被正确读出；级联传播在 XmlMerger 层测
    assert _Cpu.foreign_keys == [ForeignKeyRef("irq_ref", "irq", "irq_id")]
