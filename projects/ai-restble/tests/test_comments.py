"""Tests for ecfg.schema._comments — ruamel 注释 API 封装。

两层测试：
1. 驱动 ``_comments.py`` 自身的 doctest（把文档里的例子跑一遍）
2. 额外的 pytest 场景（doctest 不擅长的 mapping 值 + 嵌套 + 负路径）
"""
from __future__ import annotations

import doctest

from ruamel.yaml import YAML

from ecfg.schema import _comments
from ecfg.schema._comments import trailing_comment


def test_doctests_all_pass():
    """doctest 集合整体通过。"""
    result = doctest.testmod(_comments, verbose=False)
    assert result.failed == 0, f"{result.failed}/{result.attempted} doctest failures"


def _load(src: str):
    yaml = YAML(typ="rt")
    return yaml.load(src)


class TestTrailingOnScalarFields:
    def test_range_annotation(self):
        doc = _load("vector: 10  # @range: 0-255\n")
        assert trailing_comment(doc, "vector") == "@range: 0-255"

    def test_enum_annotation(self):
        doc = _load("trigger: edge  # @enum: edge, level\n")
        assert trailing_comment(doc, "trigger") == "@enum: edge, level"

    def test_fk_notation(self):
        """ref 子字段的 FK 记号（不带 @）。"""
        doc = _load("moduleType: uart  # Module.moduleType\n")
        assert trailing_comment(doc, "moduleType") == "Module.moduleType"


class TestTrailingOnMappingValue:
    def test_ref_entry_key_with_trailing_conflict(self):
        """ref 入口（mapping 值）尾行的 @merge 注释。"""
        src = (
            "owner_module:  # @merge: conflict\n"
            "  moduleType: uart\n"
            "  moduleIndex: 0\n"
        )
        doc = _load(src)
        assert trailing_comment(doc, "owner_module") == "@merge: conflict"

    def test_children_comments_still_reachable(self):
        src = (
            "owner_module:  # @merge: conflict\n"
            "  moduleType: uart  # Module.moduleType\n"
            "  moduleIndex: 0    # Module.moduleIndex\n"
        )
        doc = _load(src)
        inner = doc["owner_module"]
        assert trailing_comment(inner, "moduleType") == "Module.moduleType"
        assert trailing_comment(inner, "moduleIndex") == "Module.moduleIndex"


class TestEmptyAndMissing:
    def test_key_without_comment_returns_none(self):
        doc = _load("description:\n")
        assert trailing_comment(doc, "description") is None

    def test_key_not_present(self):
        doc = _load("a: 1\n")
        assert trailing_comment(doc, "nope") is None

    def test_value_with_hash_in_string_not_treated_as_comment(self):
        """YAML 引号内的 # 是字符串一部分，不是注释。"""
        doc = _load("name: 'a#b'\n")
        assert trailing_comment(doc, "name") is None


class TestTrailingNotPickedUpFromStandalone:
    """同行尾随注释 + 下一行 standalone 共存时，trailing_comment 只取尾随部分."""

    def test_trailing_isolated_from_standalone(self):
        src = (
            "priority: 0  # @merge: sum\n"
            "# @range: 0-15\n"
        )
        doc = _load(src)
        assert trailing_comment(doc, "priority") == "@merge: sum"
