"""YAML 文件 → Table。支持单表文件和整个目录两种入口。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from ruamel.yaml import YAML

from ecfg.model import CellValue, Record, Table
from ecfg.schema.const import REGION_ATTRIBUTE, REGION_INDEX, REGION_REF


def read_yaml_file(yaml_path: Path) -> Table:
    """读单个 ``<BaseName>.yaml`` 文件，返回对应 Table。"""
    yaml = YAML(typ="rt")
    with yaml_path.open("r", encoding="utf-8") as f:
        raw = yaml.load(f) or []
    if not isinstance(raw, list):
        raise ValueError(
            f"{yaml_path}: 顶层必须是 YAML list（每个条目是 {{index, attribute, ref?}}）"
        )
    records = [_parse_record(yaml_path, idx, item) for idx, item in enumerate(raw)]
    return Table(base_name=yaml_path.stem, records=records, source_hint=yaml_path.name)


def read_yaml_dir(dir_path: Path) -> List[Table]:
    """读目录下所有 ``*.yaml`` 文件，按文件名排序。"""
    if not dir_path.is_dir():
        raise NotADirectoryError(f"{dir_path} 不是目录")
    return [read_yaml_file(p) for p in sorted(dir_path.glob("*.yaml"))]


def _parse_record(src: Path, idx: int, item: Any) -> Record:
    """把 YAML 条目转成 Record；只接受 dict 结构，其它 raise。"""
    if not isinstance(item, dict):
        raise ValueError(
            f"{src}: 第 {idx} 条记录不是 mapping，而是 {type(item).__name__}"
        )
    return Record(
        index=_coerce_field_map(item.get(REGION_INDEX)),
        attribute=_coerce_field_map(item.get(REGION_ATTRIBUTE)),
        ref=_coerce_field_map(item.get(REGION_REF)),
    )


def _coerce_field_map(v: Any) -> Dict[str, CellValue]:
    """缺席或 None → {}；否则转成朴素 dict（剥 ruamel 的 CommentedMap 外衣）。"""
    if v is None:
        return {}
    if not isinstance(v, dict):
        raise ValueError(f"期望 mapping，实际 {type(v).__name__}: {v!r}")
    return dict(v)
