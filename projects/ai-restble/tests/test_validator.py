"""Tests for ecfg.schema.validator — schema 不变量 + 运行期数据校验."""
from __future__ import annotations

import pytest

from ecfg.model import Record, Table
from ecfg.schema.model import FieldSchema, TableSchema
from ecfg.schema.validator import ValidationError, validate_schema, validate_table


def _schema(*, index=None, attrs=None, refs=None):
    """快速 schema 构造器（attrs/refs: dict[name, FieldSchema kwargs]）."""
    s = TableSchema(base_name="T")
    s.index_fields = list(index or [])
    s.attribute_fields = {
        n: FieldSchema(name=n, region="attribute", **kw)
        for n, kw in (attrs or {}).items()
    }
    s.ref_fields = {
        n: FieldSchema(name=n, region="ref", **kw)
        for n, kw in (refs or {}).items()
    }
    return s


class TestValidateSchema:
    """schema 加载期不变量."""

    def test_clean_schema_passes(self):
        validate_schema(_schema(index=["v"], attrs={"h": {}}))

    def test_index_in_attribute_raises(self):
        with pytest.raises(ValidationError, match="同时在 attribute"):
            validate_schema(_schema(index=["v"], attrs={"v": {}}))

    def test_index_in_ref_raises(self):
        with pytest.raises(ValidationError, match="同时在 ref"):
            validate_schema(_schema(index=["v"], refs={"v": {}}))


class TestIndexUniqueness:
    def test_unique_passes(self):
        """各 index 唯一 → 通过."""
        s = _schema(index=["v"])
        t = Table(base_name="T", records=[
            Record(index={"v": 1}),
            Record(index={"v": 2}),
        ])
        validate_table(t, s)

    def test_duplicate_raises(self):
        """默认严格：同 index 重复 → ValidationError."""
        s = _schema(index=["v"])
        t = Table(base_name="T", records=[
            Record(index={"v": 1}),
            Record(index={"v": 1}),
        ])
        with pytest.raises(ValidationError, match="重复 index"):
            validate_table(t, s)

    def test_duplicate_tolerated_when_index_repeatable(self):
        """``schema.index_repeatable=True`` → 跳过唯一性检查（merger 后续分流）."""
        s = _schema(index=["v"])
        s.index_repeatable = True
        t = Table(base_name="T", records=[
            Record(index={"v": 1}),
            Record(index={"v": 1}),
        ])
        validate_table(t, s)  # 不抛

    def test_composite_index_uniqueness(self):
        """复合 index：(vector, owner_team) 整体不重复即可."""
        s = _schema(index=["vector", "owner_team"])
        t = Table(base_name="T", records=[
            Record(index={"vector": 10, "owner_team": "a"}),
            Record(index={"vector": 10, "owner_team": "b"}),  # vector 重，但 team 不同 ✓
        ])
        validate_table(t, s)


class TestRangeConstraint:
    def test_value_in_range_passes(self):
        s = _schema(attrs={"p": {"range_lo": 0, "range_hi": 15}})
        t = Table(base_name="T", records=[Record(attribute={"p": 5})])
        validate_table(t, s)

    def test_value_below_range_raises(self):
        s = _schema(attrs={"p": {"range_lo": 0, "range_hi": 15}})
        t = Table(base_name="T", records=[Record(attribute={"p": -1})])
        with pytest.raises(ValidationError, match="越界"):
            validate_table(t, s)

    def test_value_above_range_raises(self):
        s = _schema(attrs={"p": {"range_lo": 0, "range_hi": 15}})
        t = Table(base_name="T", records=[Record(attribute={"p": 99})])
        with pytest.raises(ValidationError, match="越界"):
            validate_table(t, s)

    def test_non_numeric_in_range_raises(self):
        s = _schema(attrs={"p": {"range_lo": 0, "range_hi": 15}})
        t = Table(base_name="T", records=[Record(attribute={"p": "hi"})])
        with pytest.raises(ValidationError, match="非数值"):
            validate_table(t, s)

    def test_bool_not_treated_as_int_in_range(self):
        """True 在 Python 是 int 子类；range 校验显式拒掉避免 ``True ≤ 1`` 的尴尬."""
        s = _schema(attrs={"p": {"range_lo": 0, "range_hi": 15}})
        t = Table(base_name="T", records=[Record(attribute={"p": True})])
        with pytest.raises(ValidationError, match="非数值"):
            validate_table(t, s)

    def test_missing_field_skips_range(self):
        s = _schema(attrs={"p": {"range_lo": 0, "range_hi": 15}})
        t = Table(base_name="T", records=[Record(attribute={})])  # p 缺失
        validate_table(t, s)  # 不抛


class TestEnumConstraint:
    def test_value_in_enum_passes(self):
        s = _schema(attrs={"trigger": {"enum_values": ["edge", "level"]}})
        t = Table(base_name="T", records=[Record(attribute={"trigger": "edge"})])
        validate_table(t, s)

    def test_value_not_in_enum_raises(self):
        s = _schema(attrs={"trigger": {"enum_values": ["edge", "level"]}})
        t = Table(base_name="T", records=[Record(attribute={"trigger": "rising"})])
        with pytest.raises(ValidationError, match="不在 enum 集"):
            validate_table(t, s)

    def test_missing_field_skips_enum(self):
        s = _schema(attrs={"trigger": {"enum_values": ["edge", "level"]}})
        t = Table(base_name="T", records=[Record(attribute={})])
        validate_table(t, s)
