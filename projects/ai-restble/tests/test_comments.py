"""Tests for ecfg.schema._comments — ruamel 注释 API 封装。

两层测试：
1. 驱动 ``_comments.py`` 自身的 doctest（把文档里的例子跑一遍）
2. 额外的 pytest 场景（doctest 不擅长的 mapping 值 + 嵌套 + 负路径）
"""
from __future__ import annotations

import doctest

from ruamel.yaml import YAML

from ecfg.schema import _comments
from ecfg.schema._comments import subsequent_comments, trailing_comment


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


class TestSubsequentComments:
    def test_none_when_no_standalone(self):
        doc = _load("priority: 0  # @merge: sum\n")
        assert subsequent_comments(doc, "priority") == []

    def test_single_standalone(self):
        src = "priority: 0\n# @noconflict_group: [p]\n"
        doc = _load(src)
        assert subsequent_comments(doc, "priority") == ["@noconflict_group: [p]"]

    def test_multiple_standalones(self):
        src = (
            "priority: 0\n"
            "# note one\n"
            "# @flag: x\n"
            "# note two\n"
        )
        doc = _load(src)
        assert subsequent_comments(doc, "priority") == [
            "note one", "@flag: x", "note two",
        ]

    def test_standalone_attaches_to_last_key_of_inner_mapping(self):
        """ruamel 把 standalone 挂到前一条 key —— 最深 mapping 的最后 key。"""
        src = (
            "items:\n"
            "  - ref:\n"
            "      owner:\n"
            "        moduleType: uart\n"
            "        moduleIndex: 0\n"
            "# @noconflict_group: [a, b]\n"
        )
        doc = _load(src)
        inner = doc["items"][0]["ref"]["owner"]
        assert subsequent_comments(inner, "moduleIndex") == ["@noconflict_group: [a, b]"]


class TestCoexistence:
    """同行 trailing + 下行 standalone 同时出现时两者互不干扰。"""

    def test_trailing_plus_standalone(self):
        src = (
            "priority: 0  # @merge: sum\n"
            "# @noconflict_group: [p]\n"
        )
        doc = _load(src)
        assert trailing_comment(doc, "priority") == "@merge: sum"
        assert subsequent_comments(doc, "priority") == ["@noconflict_group: [p]"]
