"""Canonical in-memory model. 所有 IO (excel/xml/yaml/web) 围绕 Table/Record 中转。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

Scalar = Union[bool, int, float, str]
"""单值字段的合法 Python 类型。"""

CellValue = Optional[Union[bool, int, float, str, List[Union[bool, int, float, str]]]]
"""记录字段的统一表示：标量、标量列表（多值字段），或 None（未设置）。"""


@dataclass
class Record:
    """一条记录的三区域视图：index(身份)、attribute(自持)、ref(关联)。"""

    index: Dict[str, CellValue] = field(default_factory=dict)
    attribute: Dict[str, CellValue] = field(default_factory=dict)
    ref: Dict[str, CellValue] = field(default_factory=dict)

    def all_fields(self) -> Dict[str, CellValue]:
        """返回三区域合并后的扁平视图（同名键按 index > attribute > ref 优先）。"""
        merged: Dict[str, CellValue] = {}
        merged.update(self.ref)
        merged.update(self.attribute)
        merged.update(self.index)
        return merged


@dataclass
class Table:
    """一张表：BaseName + 一串 Record；source_hint 用于落盘时的溯源注释。"""

    base_name: str
    records: List[Record] = field(default_factory=list)
    source_hint: Optional[str] = None
