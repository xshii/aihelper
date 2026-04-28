"""Tests for ecfg.schema.loader — TEMPLATE 块解析 + TableSchema 构建."""
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from ecfg.schema.loader import extract_template_text, load_table_schema


class TestExtractTemplateText:
    """剥 TEMPLATE BEGIN/END 块 + 去 ``# `` 前缀."""

    def test_no_template_block_returns_none(self):
        text = "- index:\n    vector: 10\n  attribute:\n    handler: h\n"
        assert extract_template_text(text) is None

    def test_basic_template_block_stripped(self):
        text = dedent("""\
            # ----- TEMPLATE BEGIN -----
            # - index:
            #     vector: 0
            #   attribute:
            #     handler: h0
            # ----- TEMPLATE END -----

            - index:
                vector: 10
        """)
        result = extract_template_text(text)
        assert result is not None
        assert "vector: 0" in result
        assert "handler: h0" in result
        # 剥前缀后是合法 yaml
        assert not result.startswith("#")

    def test_template_block_preserves_eol_comments(self):
        text = dedent("""\
            # ----- TEMPLATE BEGIN -----
            # - index:
            #     vector: 0                   # @range: 0-255
            # ----- TEMPLATE END -----
        """)
        result = extract_template_text(text)
        assert result is not None
        assert "@range: 0-255" in result


class TestLoadTableSchemaFromInterruptFixture:
    """端到端：加载 examples/tables/Interrupt.yaml ground-truth 验证 schema."""

    @pytest.fixture
    def schema(self):
        path = Path(__file__).parent.parent / "examples" / "tables" / "Interrupt.yaml"
        assert path.is_file(), f"fixture 缺失：{path}"
        return load_table_schema(path)

    def test_base_name_from_stem(self, schema):
        assert schema.base_name == "Interrupt"

    def test_index_fields_in_order(self, schema):
        assert schema.index_fields == ["vector", "owner_team"]

    def test_handler_merge_rule_concat(self, schema):
        assert schema.attribute_fields["handler"].merge_rule == "concat(',')"

    def test_priority_has_both_merge_and_range(self, schema):
        f = schema.attribute_fields["priority"]
        assert f.merge_rule == "concat(',')"
        assert f.range_lo == 0.0 and f.range_hi == 15.0

    def test_retry_merge_rule_sum(self, schema):
        assert schema.attribute_fields["retry"].merge_rule == "sum"

    def test_trigger_enum(self, schema):
        assert schema.attribute_fields["trigger"].enum_values == ["edge", "level"]

    def test_owner_team_index_enum(self, schema):
        # MVP loader 当前不为 index 字段构 FieldSchema；此 test 是占位 reminder
        # 如果后续扩展加上 index_field schemas，把 None 改成预期值
        assert schema.index_fields[1] == "owner_team"

    def test_owner_module_ref_merge_conflict(self, schema):
        f = schema.ref_fields["owner_module"]
        assert f.merge_rule == "conflict"
        assert f.fk_target == "Module.moduleType"


class TestEmptyOrAbsentTemplate:
    def test_no_template_returns_empty_schema(self, tmp_path):
        """无 TEMPLATE 块 → 空 schema（所有字段默认无约束）."""
        p = tmp_path / "Foo.yaml"
        p.write_text("- index:\n    id: 1\n", encoding="utf-8")
        s = load_table_schema(p)
        assert s.base_name == "Foo"
        assert s.index_fields == []
        assert s.attribute_fields == {}
        assert s.ref_fields == {}


class TestIndexRepeatable:
    """``# @index:repeatable`` 挂在 TEMPLATE 块 ``index:`` 行尾时被识别."""

    def test_default_not_repeatable(self):
        """Interrupt fixture 没标记 → index_repeatable=False."""
        path = Path(__file__).parent.parent / "examples" / "tables" / "Interrupt.yaml"
        assert load_table_schema(path).index_repeatable is False

    def test_annotation_picked_up(self, tmp_path):
        """``index:`` 行尾标 ``# @index:repeatable`` → schema.index_repeatable=True."""
        p = tmp_path / "Foo.yaml"
        p.write_text(dedent("""\
            # ----- TEMPLATE BEGIN -----
            # - index:                   # @index:repeatable
            #     vector: 0
            #   attribute:
            #     handler: h0             # @merge: concat(',')
            # ----- TEMPLATE END -----
        """), encoding="utf-8")
        assert load_table_schema(p).index_repeatable is True

    def test_unknown_index_value_raises(self, tmp_path):
        """未知 ``@index:<X>`` 值立即报错，避免静默 fallback 让弱 AI 误以为生效."""
        p = tmp_path / "Foo.yaml"
        p.write_text(dedent("""\
            # ----- TEMPLATE BEGIN -----
            # - index:                   # @index:nonrepeatable
            #     vector: 0
            #   attribute:
            #     handler: h0
            # ----- TEMPLATE END -----
        """), encoding="utf-8")
        with pytest.raises(ValueError, match="未知 @index 值"):
            load_table_schema(p)
