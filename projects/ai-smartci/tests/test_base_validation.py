"""MergeStrategy.__init_subclass__ 的必填 ClassVar 校验测试"""
from __future__ import annotations

import pytest

from smartci.resource_merge.strategies.base import ConflictPolicy, MergeStrategy


def test_missing_resource_type_raises():
    with pytest.raises(TypeError, match="resource_type 未声明"):
        class _X(MergeStrategy):
            selector_xpath = "//x"
            fields = {"id": "@id"}
            key_fields = ["id"]


def test_missing_selector_xpath_raises():
    with pytest.raises(TypeError, match="selector_xpath 未声明"):
        class _X(MergeStrategy):
            resource_type = "x"
            fields = {"id": "@id"}
            key_fields = ["id"]


def test_missing_fields_raises():
    with pytest.raises(TypeError, match="fields 未声明"):
        class _X(MergeStrategy):
            resource_type = "x"
            selector_xpath = "//x"
            key_fields = ["id"]


def test_missing_key_fields_raises():
    with pytest.raises(TypeError, match="key_fields 未声明"):
        class _X(MergeStrategy):
            resource_type = "x"
            selector_xpath = "//x"
            fields = {"id": "@id"}


def test_key_fields_unknown_name_raises():
    with pytest.raises(TypeError, match="包含未在 fields 声明的字段"):
        class _X(MergeStrategy):
            resource_type = "x"
            selector_xpath = "//x"
            fields = {"id": "@id"}
            key_fields = ["id", "unknown"]


def test_count_field_not_in_fields_raises():
    with pytest.raises(TypeError, match="count_field.*必须也在 fields"):
        class _X(MergeStrategy):
            resource_type = "x"
            selector_xpath = "//x"
            fields = {"id": "@id"}
            key_fields = ["id"]
            count_field = "number"   # "number" 不在 fields 里


def test_well_formed_subclass_succeeds():
    class _X(MergeStrategy):
        resource_type = "x"
        selector_xpath = "//x"
        fields = {"id": "@id", "num": "@num"}
        key_fields = ["id"]
        count_field = "num"
        conflict_policy = ConflictPolicy.ERROR

    # 能实例化且 resource_type/key_fields 可读
    s = _X()
    assert s.resource_type == "x"
    assert list(s.key_fields) == ["id"]
