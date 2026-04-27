"""Table → XML exporter（硬件下游 / 友邻部门消费的最终格式）。

输出格式::

    <merged>
      <{BaseName}>
        <item {scalar_field}="..." ...>
          <{list_field}>v1</{list_field}>
          <{list_field}>v2</{list_field}>
        </item>
      </{BaseName}>
    </merged>
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from lxml import etree

from ecfg.model import CellValue, Record, Table

_ROOT_TAG = "merged"
_ITEM_TAG = "item"
_ENCODING = "utf-8"


def write_tables(
    tables: List[Table], output_path: Path, *, force: bool = False,
) -> Path:
    """多张 Table 合写一份 XML。目标已存在且非 force 时 raise。"""
    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} 已存在；使用 --force 覆盖")
    root = etree.Element(_ROOT_TAG)
    for table in tables:
        container = etree.SubElement(root, table.base_name)
        for rec in table.records:
            _append_item(container, rec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree = etree.ElementTree(root)
    tree.write(
        str(output_path),
        pretty_print=True, xml_declaration=True, encoding=_ENCODING,
    )
    return output_path


def _append_item(container: etree._Element, rec: Record) -> None:
    """为一条 Record 追加 ``<item>``：标量字段 → attribute，list → child 元素。"""
    node = etree.SubElement(container, _ITEM_TAG)
    flat = rec.all_fields()
    for name, value in flat.items():
        if value is None:
            continue
        if isinstance(value, list):
            for v in value:
                child = etree.SubElement(node, name)
                child.text = _scalar_to_text(v)
        else:
            node.set(name, _scalar_to_text(value))


def _scalar_to_text(v: CellValue) -> str:
    """Scalar → XML 文本表示；bool → 'true'/'false'，其它 str()。"""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)
