"""Tests for ecfg.merge — 6 merge ops + multi-team 合并端到端."""
from __future__ import annotations

import pytest

from ecfg.merge import ConflictError, apply_merge, merge_tables
from ecfg.merge.policies import parse_merge_rule  # 内部 helper，不在 facade
from ecfg.model import Record, Table
from ecfg.schema.model import FieldSchema, TableSchema
from ecfg.schema.validator import ValidationError


class TestParseMergeRule:
    def test_concat_with_string_arg(self):
        assert parse_merge_rule("concat(',')") == ("concat", ",")

    def test_concat_double_quoted(self):
        assert parse_merge_rule('concat("; ")') == ("concat", "; ")

    def test_bare_op(self):
        assert parse_merge_rule("sum") == ("sum", None)
        assert parse_merge_rule("conflict") == ("conflict", None)


class TestApplyMerge:
    def test_concat_strings(self):
        assert apply_merge("concat(',')", ["a", "b", "c"]) == "a,b,c"

    def test_concat_skips_none(self):
        assert apply_merge("concat(',')", ["a", None, "b"]) == "a,b"

    def test_sum_ints(self):
        assert apply_merge("sum", [1, 2, 3]) == 6

    def test_max_min(self):
        assert apply_merge("max", [3, 1, 4, 1, 5]) == 5
        assert apply_merge("min", [3, 1, 4, 1, 5]) == 1

    def test_union_dedups_preserve_order(self):
        assert apply_merge("union", ["a", "b", "a", "c"]) == ["a", "b", "c"]

    def test_conflict_all_equal_returns_value(self):
        assert apply_merge("conflict", ["x", "x", "x"]) == "x"

    def test_conflict_disagreement_raises(self):
        with pytest.raises(ConflictError):
            apply_merge("conflict", ["x", "y"])

    def test_unknown_op_raises(self):
        with pytest.raises(ValueError, match="未知 merge op"):
            apply_merge("nosuch", [1, 2])


def _make_schema(
    *,
    index_fields=None,
    attribute_rules=None,
    ref_rules=None,
):
    """快速构造 TableSchema（attribute_rules: dict[name, merge_rule]）."""
    s = TableSchema(base_name="Test")
    s.index_fields = list(index_fields or [])
    s.attribute_fields = {
        n: FieldSchema(name=n, region="attribute", merge_rule=r)
        for n, r in (attribute_rules or {}).items()
    }
    s.ref_fields = {
        n: FieldSchema(name=n, region="ref", merge_rule=r)
        for n, r in (ref_rules or {}).items()
    }
    return s


class TestMergeTablesSingleTable:
    def test_no_grouping_passthrough(self):
        schema = _make_schema(index_fields=["id"])
        t = Table(base_name="Test", records=[
            Record(index={"id": 1}, attribute={"x": "a"}),
            Record(index={"id": 2}, attribute={"x": "b"}),
        ])
        merged = merge_tables([t], schema)
        assert len(merged.records) == 2


class TestMergeTablesTwoTablesSameIndex:
    def test_concat_handler_across_teams(self):
        schema = _make_schema(
            index_fields=["vector"],
            attribute_rules={"handler": "concat(',')"},
        )
        a = Table(base_name="Test", records=[
            Record(index={"vector": 10}, attribute={"handler": "h_a"}),
        ])
        b = Table(base_name="Test", records=[
            Record(index={"vector": 10}, attribute={"handler": "h_b"}),
        ])
        merged = merge_tables([a, b], schema)
        assert len(merged.records) == 1
        assert merged.records[0].attribute["handler"] == "h_a,h_b"

    def test_sum_retry(self):
        schema = _make_schema(
            index_fields=["vector"],
            attribute_rules={"retry": "sum"},
        )
        a = Table(base_name="Test", records=[
            Record(index={"vector": 10}, attribute={"retry": 3}),
        ])
        b = Table(base_name="Test", records=[
            Record(index={"vector": 10}, attribute={"retry": 4}),
        ])
        merged = merge_tables([a, b], schema)
        assert merged.records[0].attribute["retry"] == 7

    def test_conflict_field_disagreement_raises(self):
        schema = _make_schema(
            index_fields=["vector"],
            attribute_rules={"trigger": "conflict"},
        )
        a = Table(base_name="Test", records=[
            Record(index={"vector": 10}, attribute={"trigger": "edge"}),
        ])
        b = Table(base_name="Test", records=[
            Record(index={"vector": 10}, attribute={"trigger": "level"}),
        ])
        with pytest.raises(ConflictError) as excinfo:
            merge_tables([a, b], schema)
        # 错误信息应同时包含表名 / index 标识 / region / 字段名 / 实际差异值
        msg = str(excinfo.value)
        assert "Test[vector=10].attribute.trigger" in msg
        assert "edge" in msg and "level" in msg

    def test_conflict_field_agreement_kept(self):
        schema = _make_schema(
            index_fields=["vector"],
            attribute_rules={"trigger": "conflict"},
        )
        a = Table(base_name="Test", records=[
            Record(index={"vector": 10}, attribute={"trigger": "edge"}),
        ])
        b = Table(base_name="Test", records=[
            Record(index={"vector": 10}, attribute={"trigger": "edge"}),
        ])
        merged = merge_tables([a, b], schema)
        assert merged.records[0].attribute["trigger"] == "edge"


class TestUnruledFieldDifference:
    """无 @merge 规则的字段差异 → 取首条 non-None（merge-spec.md §6.3）."""

    def test_takes_first_non_none(self):
        schema = _make_schema(index_fields=["id"])
        a = Table(base_name="Test", records=[
            Record(index={"id": 1}, attribute={"description": "first"}),
        ])
        b = Table(base_name="Test", records=[
            Record(index={"id": 1}, attribute={"description": "second"}),
        ])
        merged = merge_tables([a, b], schema)
        assert merged.records[0].attribute["description"] == "first"


class TestRefRegionDefaultConflict:
    """ref 区无显式规则时默认 ``conflict``（必须等值）."""

    def test_ref_agreement_kept(self):
        schema = _make_schema(index_fields=["id"])
        a = Table(base_name="Test", records=[
            Record(
                index={"id": 1},
                ref={"owner": "{moduleType: uart, moduleIndex: 0}"},
            ),
        ])
        b = Table(base_name="Test", records=[
            Record(
                index={"id": 1},
                ref={"owner": "{moduleType: uart, moduleIndex: 0}"},
            ),
        ])
        merged = merge_tables([a, b], schema)
        assert merged.records[0].ref["owner"] == "{moduleType: uart, moduleIndex: 0}"

    def test_ref_disagreement_raises(self):
        schema = _make_schema(index_fields=["id"])
        a = Table(base_name="Test", records=[
            Record(index={"id": 1}, ref={"owner": "uart"}),
        ])
        b = Table(base_name="Test", records=[
            Record(index={"id": 1}, ref={"owner": "spi"}),
        ])
        with pytest.raises(ConflictError) as excinfo:
            merge_tables([a, b], schema)
        # ref 区错误信息也应有 region 区分
        assert "Test[id=1].ref.owner" in str(excinfo.value)


class TestMergeValidatesByDefault:
    """``merge_tables`` 默认开校验；脏输入抛 ValidationError 而非静默错合."""

    def test_range_violation_blocks_merge(self):
        schema = _make_schema(
            index_fields=["v"],
            attribute_rules={"priority": "concat(',')"},
        )
        schema.attribute_fields["priority"].range_lo = 0
        schema.attribute_fields["priority"].range_hi = 15
        bad = Table(base_name="Test", records=[
            Record(index={"v": 1}, attribute={"priority": 999}),
        ])
        with pytest.raises(ValidationError, match="越界"):
            merge_tables([bad], schema)

    def test_duplicate_index_within_table_blocks_merge(self):
        schema = _make_schema(index_fields=["v"])
        bad = Table(base_name="Test", records=[
            Record(index={"v": 1}),
            Record(index={"v": 1}),
        ])
        with pytest.raises(ValidationError, match="重复 index"):
            merge_tables([bad], schema)

    def test_validate_false_bypasses(self):
        """``validate=False`` 旁路所有校验（已知干净的 in-memory 数据）."""
        schema = _make_schema(
            index_fields=["v"],
            attribute_rules={"priority": "concat(',')"},
        )
        schema.attribute_fields["priority"].range_lo = 0
        schema.attribute_fields["priority"].range_hi = 15
        bad = Table(base_name="Test", records=[
            Record(index={"v": 1}, attribute={"priority": 999}),
        ])
        merged = merge_tables([bad], schema, validate=False)
        assert merged.records[0].attribute["priority"] == 999


class TestIntraTableRepeatable:
    """``@index:repeatable`` 表内重复的三档语义（用户场景 1/2/3）."""

    def test_all_identical_dups_collapse(self):
        """场景 1：完全相同的两条 → 合一（幂等）."""
        schema = _make_schema(
            index_fields=["v"],
            attribute_rules={"handler": "concat(',')"},
        )
        schema.index_repeatable = True
        t = Table(base_name="Test", records=[
            Record(index={"v": 1}, attribute={"handler": "h"}),
            Record(index={"v": 1}, attribute={"handler": "h"}),  # 相同
        ])
        merged = merge_tables([t], schema)
        assert len(merged.records) == 1
        assert merged.records[0].attribute["handler"] == "h"  # 短路保留原值，不 concat

    def test_mergeable_dups_resolve_via_rule(self):
        """场景 2：差异字段都有 @merge 规则 → 按规则合."""
        schema = _make_schema(
            index_fields=["v"],
            attribute_rules={"handler": "concat(',')", "retry": "sum"},
        )
        schema.index_repeatable = True
        t = Table(base_name="Test", records=[
            Record(index={"v": 1}, attribute={"handler": "h_a", "retry": 2}),
            Record(index={"v": 1}, attribute={"handler": "h_b", "retry": 3}),
        ])
        merged = merge_tables([t], schema)
        assert len(merged.records) == 1
        assert merged.records[0].attribute["handler"] == "h_a,h_b"
        assert merged.records[0].attribute["retry"] == 5

    def test_unmergeable_dups_raise_with_context(self):
        """场景 3：差异字段无 @merge 或 @merge:conflict → ConflictError + 完整定位."""
        schema = _make_schema(
            index_fields=["v"],
            attribute_rules={"trigger": "conflict"},
        )
        schema.index_repeatable = True
        t = Table(base_name="Test", records=[
            Record(index={"v": 1}, attribute={"trigger": "edge"}),
            Record(index={"v": 1}, attribute={"trigger": "level"}),
        ])
        with pytest.raises(ConflictError) as excinfo:
            merge_tables([t], schema)
        assert "Test[v=1].attribute.trigger" in str(excinfo.value)


class TestMergeThreeTeams:
    """merge-spec §6.2：3 team 同 index，并列 concat + sum."""

    def test_three_team_aggregation(self):
        schema = _make_schema(
            index_fields=["vector"],
            attribute_rules={
                "handler": "concat(',')",
                "priority": "concat(',')",
                "retry": "sum",
            },
        )
        teams = [
            Table(base_name="Test", records=[
                Record(index={"vector": 10}, attribute={
                    "handler": "h1", "priority": 2, "retry": 3,
                }),
            ]),
            Table(base_name="Test", records=[
                Record(index={"vector": 10}, attribute={
                    "handler": "h2", "priority": 5, "retry": 4,
                }),
            ]),
            Table(base_name="Test", records=[
                Record(index={"vector": 10}, attribute={
                    "handler": "h3", "priority": 1, "retry": 2,
                }),
            ]),
        ]
        merged = merge_tables(teams, schema)
        assert merged.records[0].attribute["handler"] == "h1,h2,h3"
        assert merged.records[0].attribute["priority"] == "2,5,1"
        assert merged.records[0].attribute["retry"] == 9
