"""Tests for ecfg.schema.annotations.parse_comment — 对照 docs/merge-spec.md §2.4。"""
from __future__ import annotations

from ecfg.schema.annotations import Annotation, ParsedComment, parse_comment


class TestEmptyAndWhitespace:
    def test_empty_string(self):
        assert parse_comment("") == ParsedComment([], [])

    def test_only_whitespace(self):
        assert parse_comment("   ") == ParsedComment([], [])

    def test_only_separators(self):
        assert parse_comment(";;;") == ParsedComment([], [])

    def test_separators_and_whitespace(self):
        assert parse_comment(" ; ; ") == ParsedComment([], [])


class TestSingleAnnotation:
    def test_range(self):
        r = parse_comment("@range: 0-15")
        assert r.annotations == [Annotation("range", "0-15")]
        assert r.freeform == []

    def test_enum_with_commas(self):
        r = parse_comment("@enum: edge, level")
        assert r.annotations == [Annotation("enum", "edge, level")]

    def test_merge_concat(self):
        r = parse_comment("@merge: concat(',')")
        assert r.annotations == [Annotation("merge", "concat(',')")]

    def test_merge_conflict(self):
        r = parse_comment("@merge: conflict")
        assert r.annotations == [Annotation("merge", "conflict")]

    def test_leading_whitespace(self):
        r = parse_comment("  @range:   0-15  ")
        assert r.annotations == [Annotation("range", "0-15")]

    def test_key_with_underscore(self):
        r = parse_comment("@noconflict_group: [handler, priority]")
        assert r.annotations == [Annotation("noconflict_group", "[handler, priority]")]


class TestTwoAnnotations:
    """spec §2.4 的核心 case：同一注释出现两个 annotation。"""

    def test_range_and_merge(self):
        r = parse_comment("@range: 0-15; @merge: concat(',')")
        assert r.annotations == [
            Annotation("range", "0-15"),
            Annotation("merge", "concat(',')"),
        ]
        assert r.freeform == []

    def test_range_and_enum(self):
        r = parse_comment("@range: 0-255; @enum: 0, 16, 32, 64")
        assert r.annotations == [
            Annotation("range", "0-255"),
            Annotation("enum", "0, 16, 32, 64"),
        ]

    def test_merge_conflict_and_unit(self):
        r = parse_comment("@merge: conflict; @unit: Hz")
        assert r.annotations == [
            Annotation("merge", "conflict"),
            Annotation("unit", "Hz"),
        ]

    def test_extra_whitespace_around_separator(self):
        r = parse_comment("@range: 0-15  ;  @merge: concat(',')")
        assert r.annotations == [
            Annotation("range", "0-15"),
            Annotation("merge", "concat(',')"),
        ]


class TestThreeOrMoreAnnotations:
    def test_three(self):
        r = parse_comment("@range: 0-15; @enum: 1,2,3; @merge: conflict")
        assert len(r.annotations) == 3
        assert r.annotations[0] == Annotation("range", "0-15")
        assert r.annotations[1] == Annotation("enum", "1,2,3")
        assert r.annotations[2] == Annotation("merge", "conflict")


class TestFreeformMix:
    def test_prefix_freeform(self):
        r = parse_comment("优先级越高越先响应; @range: 0-15")
        assert r.annotations == [Annotation("range", "0-15")]
        assert r.freeform == ["优先级越高越先响应"]

    def test_suffix_freeform(self):
        r = parse_comment("@range: 0-15; V2 起才支持")
        assert r.annotations == [Annotation("range", "0-15")]
        assert r.freeform == ["V2 起才支持"]

    def test_sandwich(self):
        r = parse_comment("优先级; @range: 0-15; V2 起才支持")
        assert r.annotations == [Annotation("range", "0-15")]
        assert r.freeform == ["优先级", "V2 起才支持"]

    def test_freeform_around_two_annotations(self):
        r = parse_comment("前说明; @range: 0-15; @merge: conflict; 后说明")
        assert r.annotations == [
            Annotation("range", "0-15"),
            Annotation("merge", "conflict"),
        ]
        assert r.freeform == ["前说明", "后说明"]

    def test_only_freeform(self):
        r = parse_comment("优先级越高越先响应")
        assert r.annotations == []
        assert r.freeform == ["优先级越高越先响应"]

    def test_at_not_at_start_is_freeform(self):
        """``@range`` 不在段首 → 整段 freeform，annotation 不生效。"""
        r = parse_comment("优先级 @range: 0-15")
        assert r.annotations == []
        assert r.freeform == ["优先级 @range: 0-15"]

    def test_parentheses_in_freeform(self):
        r = parse_comment("优先级（不要写 @xxx）")
        assert r.annotations == []
        assert r.freeform == ["优先级（不要写 @xxx）"]


class TestNestedSeparators:
    """括号 / 引号内的 ``;`` 不该被当成段分隔符。"""

    def test_semicolon_in_parens(self):
        r = parse_comment("@merge: concat(';')")
        assert r.annotations == [Annotation("merge", "concat(';')")]
        assert r.freeform == []

    def test_semicolon_in_brackets(self):
        r = parse_comment('@enum: ["a;b", "c"]')
        assert r.annotations == [Annotation("enum", '["a;b", "c"]')]

    def test_semicolon_in_braces(self):
        r = parse_comment("@map: {k;v: 1}")
        assert r.annotations == [Annotation("map", "{k;v: 1}")]

    def test_semicolon_in_double_quotes(self):
        r = parse_comment('@merge: concat(";")')
        assert r.annotations == [Annotation("merge", 'concat(";")')]

    def test_nested_quotes_in_parens(self):
        r = parse_comment("@merge: concat('(x;y)'); @range: 0-15")
        assert r.annotations == [
            Annotation("merge", "concat('(x;y)')"),
            Annotation("range", "0-15"),
        ]

    def test_list_with_nested_structures(self):
        r = parse_comment("@noconflict_group: [handler, priority, retry]; @merge: conflict")
        assert r.annotations == [
            Annotation("noconflict_group", "[handler, priority, retry]"),
            Annotation("merge", "conflict"),
        ]


class TestEdgeCases:
    def test_bare_at_without_colon_is_freeform(self):
        """``@foo`` 无冒号 → 整段 freeform（"参考 @张三" 这种）。"""
        r = parse_comment("@foo bar")
        assert r.annotations == []
        assert r.freeform == ["@foo bar"]

    def test_unknown_at_key_is_parsed(self):
        """未知 @ key 仍被解析；是否报警交由上层。"""
        r = parse_comment("@author: gakki")
        assert r.annotations == [Annotation("author", "gakki")]

    def test_value_with_colon(self):
        r = parse_comment("@url: https://example.com/path")
        assert r.annotations == [Annotation("url", "https://example.com/path")]

    def test_empty_value(self):
        r = parse_comment("@flag:")
        assert r.annotations == [Annotation("flag", "")]

    def test_trailing_separator(self):
        r = parse_comment("@range: 0-15;")
        assert r.annotations == [Annotation("range", "0-15")]

    def test_leading_separator(self):
        r = parse_comment(";@range: 0-15")
        assert r.annotations == [Annotation("range", "0-15")]

    def test_at_with_number_key_not_matched(self):
        """``@123`` 不合法标识符（数字开头）→ freeform。"""
        r = parse_comment("@123: x")
        assert r.annotations == []
        assert r.freeform == ["@123: x"]
