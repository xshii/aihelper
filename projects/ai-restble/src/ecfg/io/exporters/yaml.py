"""Table → YAML 文件（带溯源注释头）。落盘格式即 ecfg 的主形态。"""
from __future__ import annotations

from pathlib import Path
from typing import List, NamedTuple

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from ecfg.model import Record, Table


class WriteResult(NamedTuple):
    """单张表落盘的结果摘要。"""

    base_name: str
    output_path: Path
    row_count: int


def write_tables(
    tables: List[Table], output_dir: Path, *, force: bool = False,
) -> List[WriteResult]:
    """批量落盘 Table 到 ``<output_dir>/<BaseName>.yaml``；跳过空表。"""
    yaml = YAML()
    yaml.indent(mapping=2, sequence=2, offset=0)
    yaml.preserve_quotes = True

    results: List[WriteResult] = []
    for table in tables:
        if not table.records:
            continue
        path = output_dir / f"{table.base_name}.yaml"
        if path.exists() and not force:
            raise FileExistsError(f"{path} 已存在；使用 --force 覆盖")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            f.write(_header_comment(table))
            yaml.dump(_records_to_commented_seq(table.records), f)
        results.append(WriteResult(table.base_name, path, len(table.records)))
    return results


def _header_comment(table: Table) -> str:
    """生成 YAML 文件顶部的溯源注释头。"""
    lines = [f"# {table.base_name}.yaml"]
    if table.source_hint:
        lines.append(f"# 从 {table.source_hint} 自动生成。")
    lines.append("# 关联关系（ref）需另行补充；参见 ecfg 设计文档。")
    return "\n".join(lines) + "\n\n"


def _records_to_commented_seq(records: List[Record]) -> CommentedSeq:
    """Record → CommentedMap，保留三区域（ref 若为空则省略）顺序。"""
    seq = CommentedSeq()
    for rec in records:
        node = CommentedMap()
        node["index"] = CommentedMap(rec.index)
        node["attribute"] = CommentedMap(rec.attribute)
        if rec.ref:
            node["ref"] = CommentedMap(rec.ref)
        seq.append(node)
    return seq
