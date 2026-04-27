"""XML → Table importer.

预期输入格式（ecfg 自己的 exporter 产出的也是这个形态）::

    <merged>
      <IrqTbl>
        <item vector="10" priority="2" trigger="edge">
          <tables>t1</tables>
          <tables>t2</tables>
        </item>
      </IrqTbl>
    </merged>

* 根标签任意；直接子元素的 tag 名作为 BaseName
* 每个 ``<item>`` 的 XML 属性进 ``Record.attribute`` 的标量字段
* 同名 child 元素重复出现 → 合成为 list；单次出现 → 标量
* 不区分 index / attribute（XML 没表达这信息）；index 信息由后续 schema 或人工补
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from lxml import etree

from ecfg.model import CellValue, Record, Scalar, Table


def xml_to_tables(xml_path: Path) -> List[Table]:
    """读一份 XML，把每个直接子元素当作一张表。"""
    tree = etree.parse(str(xml_path))
    root = tree.getroot()
    tables: List[Table] = []
    for table_node in root:
        if not isinstance(table_node.tag, str):  # 跳过注释/PI
            continue
        records = [_parse_item(item) for item in table_node if _is_item(item)]
        tables.append(Table(
            base_name=table_node.tag,
            records=records,
            source_hint=xml_path.name,
        ))
    return tables


def _is_item(node: Any) -> bool:
    """过滤掉注释/PI/空白文本节点。"""
    return isinstance(node.tag, str)


def _parse_item(item: Any) -> Record:
    """``<item attr=.../>`` + child 元素 → Record（全部入 attribute 区）。"""
    attribute: Dict[str, CellValue] = {}
    for name, val in item.attrib.items():
        attribute[name] = _coerce_scalar(val)
    child_buckets: Dict[str, List[Scalar]] = {}
    for child in item:
        if not _is_item(child):
            continue
        value = _text_value(child)
        if value is None:
            continue
        child_buckets.setdefault(child.tag, []).append(value)
    for name, values in child_buckets.items():
        attribute[name] = values[0] if len(values) == 1 else values
    return Record(attribute=attribute)


def _text_value(node: Any) -> Optional[Scalar]:
    """child 元素的文本值 → Scalar；空节点返回 None。"""
    text = (node.text or "").strip()
    return _coerce_scalar(text) if text else None


def _coerce_scalar(raw: str) -> Scalar:
    """字符串还原成最精确的标量类型：bool / int / float / str。"""
    lower = raw.strip().lower()
    if lower in ("true", "false"):
        return lower == "true"
    try:
        if lower.startswith(("0x", "-0x")):
            return int(lower, 16)
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw
