"""从 yaml 文件首部 TEMPLATE BEGIN/END 块抽取并构建 ``TableSchema``.

约定（merge-spec.md §2.3）：
- TEMPLATE 块由 ``# ----- TEMPLATE BEGIN -----`` 和 ``# ----- TEMPLATE END -----`` 包裹
- 块内每行注释以 ``# `` 开头，剥前缀后是合法 YAML（含 EOL 注解）
- 块内是一条占位 record（三区域 ``index/attribute/ref``）
- 字段尾随注释承载 ``@merge / @range / @enum`` 等 annotations
- ref 区子字段尾随注释为 FK 记号 ``<BaseName>.<field>``（裸文本，无 ``@``）
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from ecfg.schema._comments import trailing_comment
from ecfg.schema.annotations import parse_comment
from ecfg.schema.model import FieldSchema, TableSchema

_YAML_RT = YAML(typ="rt")

_TEMPLATE_BEGIN = "# ----- TEMPLATE BEGIN -----"
_TEMPLATE_END = "# ----- TEMPLATE END -----"
_RANGE_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)\s*$")
_FK_RE = re.compile(r"^\s*([A-Z][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*$")


def extract_template_text(yaml_text: str) -> Optional[str]:
    """提取 TEMPLATE BEGIN/END 之间的内容，剥每行的 ``# `` 前缀。

    返回 None 表示文件无 TEMPLATE 块。
    """
    in_template = False
    out: list[str] = []
    for line in yaml_text.splitlines():
        if line.strip() == _TEMPLATE_BEGIN:
            in_template = True
            continue
        if line.strip() == _TEMPLATE_END:
            return "\n".join(out)
        if in_template:
            out.append(re.sub(r"^#\s?", "", line))
    return None  # 没找到 END（或根本没 BEGIN）


def load_table_schema(yaml_path: Path) -> TableSchema:
    """读 yaml 文件 → 构建 ``TableSchema``；无 TEMPLATE 块时返回空 schema."""
    base_name = yaml_path.stem
    text = yaml_path.read_text(encoding="utf-8")
    template_text = extract_template_text(text)
    schema = TableSchema(base_name=base_name)
    if template_text is None:
        return schema  # 无 TEMPLATE：所有字段默认无约束/无 merge 规则

    template_doc = _YAML_RT.load(template_text)
    if not template_doc:
        return schema
    record = template_doc[0]  # 占位 record

    index_map = record.get("index") or CommentedMap()
    attr_map = record.get("attribute") or CommentedMap()
    ref_map = record.get("ref") or CommentedMap()

    schema.index_fields = list(index_map.keys())
    # MVP：index 字段不构 FieldSchema（不参与 merge）；如未来 validator 需要约束信息，
    # 在此扩展构建 ``schema.index_field_schemas``。
    schema.attribute_fields = {
        name: _build_field_schema(name, "attribute", attr_map)
        for name in attr_map
    }
    schema.ref_fields = {
        name: _build_ref_field_schema(name, ref_map)
        for name in ref_map
    }
    return schema


def _build_field_schema(name: str, region: str, parent: CommentedMap) -> FieldSchema:
    """为 attribute / index 字段构建 FieldSchema."""
    fs = FieldSchema(name=name, region=region)  # type: ignore[arg-type]
    comment = trailing_comment(parent, name) or ""
    parsed = parse_comment(comment)
    for ann in parsed.annotations:
        if ann.key == "merge":
            fs.merge_rule = ann.value
        elif ann.key == "range":
            m = _RANGE_RE.match(ann.value)
            if m:
                fs.range_lo = float(m.group(1))
                fs.range_hi = float(m.group(2))
        elif ann.key == "enum":
            fs.enum_values = [v.strip() for v in ann.value.split(",") if v.strip()]
    return fs


def _build_ref_field_schema(name: str, ref_map: CommentedMap) -> FieldSchema:
    """ref 区子项：尾随 ``@merge`` 在 entry-level；FK 目标在更深的 leaf 子注释（MVP 暂不展开）."""
    fs = FieldSchema(name=name, region="ref")
    comment = trailing_comment(ref_map, name) or ""
    parsed = parse_comment(comment)
    for ann in parsed.annotations:
        if ann.key == "merge":
            fs.merge_rule = ann.value
    # FK 目标：扫子 mapping 的尾随注释（不带 @ 的裸 BaseName.field 形式）
    entry = ref_map.get(name)
    if isinstance(entry, CommentedMap):
        for sub in entry:
            sub_comment = trailing_comment(entry, sub) or ""
            m = _FK_RE.match(sub_comment)
            if m:
                # MVP：FK 信息聚合到 entry 级；只记一个目标 BaseName
                fs.fk_target = f"{m.group(1)}.{m.group(2)}"
                break
    return fs
