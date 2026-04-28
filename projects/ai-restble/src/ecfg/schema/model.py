"""Schema 内存模型：``TableSchema`` 描述一张表的字段约束 + merge 规则。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

Region = Literal["index", "attribute", "ref"]


def to_hashable(value: Any) -> Any:
    """``CellValue`` → hashable 形式：list → tuple，其他原样（用于 dict key / set 元素）."""
    if isinstance(value, list):
        return tuple(value)
    return value


@dataclass
class FieldSchema:
    """单字段 schema：name + region + 可选约束（range/enum）+ 可选 merge 规则.

    ``fk_targets``：仅 ref 区有意义。形如 ``{"moduleType": "Module.moduleType",
    "moduleIndex": "Module.moduleIndex"}``，每个子字段记一个 FK 目标。FK 闭包校验
    （所有 ``T.c`` 必须解析到现存数据）是后续工作，目前数据结构已就绪。
    """

    name: str
    region: Region
    merge_rule: Optional[str] = None  # 原始字符串，如 ``concat(',')`` / ``sum`` / ``conflict``
    range_lo: Optional[float] = None
    range_hi: Optional[float] = None
    enum_values: Optional[List[str]] = None
    fk_targets: Dict[str, str] = field(default_factory=dict)


@dataclass
class TableSchema:
    """一张表的 schema：BaseName + 三区域字段 schemas + 索引可重复 flag。

    ``index_repeatable``：默认 False（同 index 严格唯一）。声明 ``# @index:repeatable``
    （挂在 TEMPLATE 块的 ``index:`` 行尾）即放宽 — 同 index 重复由 merge 引擎按
    (1) 全等短路 / (2) 字段差异均有 ``@merge`` 规则 / (3) 真冲突 三档自动分流。
    """

    base_name: str
    index_fields: List[str] = field(default_factory=list)
    index_repeatable: bool = False
    attribute_fields: Dict[str, FieldSchema] = field(default_factory=dict)
    ref_fields: Dict[str, FieldSchema] = field(default_factory=dict)

    def merge_rule_for(self, region: Region, name: str) -> Optional[str]:
        """查找指定 region+name 字段的 merge 规则字符串；查不到返回 None."""
        if region == "attribute":
            f = self.attribute_fields.get(name)
            return f.merge_rule if f else None
        if region == "ref":
            f = self.ref_fields.get(name)
            return f.merge_rule if f else None
        return None  # index 不参与 merge
