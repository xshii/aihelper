"""Table → Excel exporter。每张 Table 一个 sheet。"""
from __future__ import annotations

from pathlib import Path
from typing import List, Set

from openpyxl import Workbook

from ecfg.model import CellValue, Record, Table

_LIST_JOIN = "|"


def write_tables(
    tables: List[Table], output_path: Path, *, force: bool = False,
) -> Path:
    """多张 Table 合写到一份 xlsx，每 Table 一个 sheet。"""
    if output_path.exists() and not force:
        raise FileExistsError(f"{output_path} 已存在；使用 --force 覆盖")
    wb = Workbook()
    default_sheet = wb.active
    if default_sheet is not None:
        wb.remove(default_sheet)
    for table in tables:
        _add_sheet(wb, table)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(output_path))
    return output_path


def _add_sheet(wb: Workbook, table: Table) -> None:
    """为一张 Table 建 sheet：列顺序 = index 字段 + attribute 字段 + ref 字段。"""
    ws = wb.create_sheet(title=table.base_name)
    columns = _collect_columns(table.records)
    ws.append(columns)
    for rec in table.records:
        flat = rec.all_fields()
        ws.append([_cell_text(flat.get(col)) for col in columns])


def _collect_columns(records: List[Record]) -> List[str]:
    """收集所有字段名，保持首条记录的 index/attribute/ref 顺序。"""
    ordered: List[str] = []
    seen: Set[str] = set()
    for rec in records:
        for region in (rec.index, rec.attribute, rec.ref):
            for k in region:
                if k not in seen:
                    seen.add(k)
                    ordered.append(k)
    return ordered


def _cell_text(v: CellValue) -> object:
    """CellValue → Excel 单元格值；list 用 ``|`` 连接。"""
    if v is None:
        return None
    if isinstance(v, list):
        return _LIST_JOIN.join(str(x) for x in v)
    return v
