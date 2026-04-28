"""按需从 legacy XML 生成 ``template/`` 下的 schema scaffold（无约束注解）.

跟 ``preprocess.unpack`` 解耦 — 主流程（XML → data yaml）不会触发此模块；
用户显式调用 ``generate_scaffolds(xml_paths, out_dir)`` 时才生成。

设计原则：
- **幂等**：多次调用同一 XML 字节级一致
- **round-trip 一致**：``XML → unpack → pack → XML`` 后再生成的 scaffold 与首次一致
- **覆盖语义**：overwrite 既有文件 — 用户编辑过的 template（带约束注解）需先备份

布局：
- 无 scope fixture: ``template/<bare_class>.yaml`` 平铺
- 有 scope fixture: ``template/shared/<bare>.yaml``（跨 scope）+
  ``template/<FAKE_RUNMODE_FOLDER>/<bare>.yaml``（scope-bound 占位）

内容：镜像 data yaml 扁平形态，所有字段值 null，EOL 注释槽供用户后填
``@merge / @range / @enum / @index`` / FK (``Table.col``) 等约束。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from ecfg.legacy._parse import (
    build_runmode_xref,
    classify,
    collect_and_dedup,
    detect_count_attr,
    scope_for,
)
from ecfg.legacy._yaml import attach_count_anchor, dump_yaml, element_header
from ecfg.legacy.const import (
    DEFAULT_CHILD_TAG,
    FAKE_RUNMODE_FOLDER,
    LINE_COUNT_ATTR,
    ROOT_TAG,
    ROOT_YAML,
    RUNMODE_TBL_TAG,
    SHARED_FOLDER,
    TEMPLATE_FOLDER,
    WRAPPER_TAG,
    strip_variant,
)

logger = logging.getLogger(__name__)


def generate_scaffolds(xml_paths: List[Path], out_dir: Path) -> None:
    """读 XML(s)，把 schema scaffold 写到 ``out_dir/template/`` 下.

    跨多 XML：同 (bare_class, scope) tuple 的字段集取**有序 union**（按 XML 出现序）。
    overwrite 既有文件；目标路径不存在时自动建。
    """
    if not xml_paths:
        raise ValueError("xml_paths 不能为空")
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    file_info_root, children = collect_and_dedup(xml_paths)
    has_scope = any(c.tag == RUNMODE_TBL_TAG for c in children)
    xref = build_runmode_xref(children) if has_scope else {}

    base = out_dir / TEMPLATE_FOLDER
    groups: Dict[Path, List[Any]] = {}
    elem_of_path: Dict[Path, str] = {}
    for child in children:
        elem_name, stem = classify(child)
        scope_folder = scope_for(child, elem_name, stem, xref, has_scope)
        bare = strip_variant(stem)
        tmpl_path = _template_path_for(base, bare, scope_folder, has_scope)
        groups.setdefault(tmpl_path, []).append(child)
        elem_of_path.setdefault(tmpl_path, elem_name)

    for tmpl_path, instances in groups.items():
        tmpl_path.parent.mkdir(parents=True, exist_ok=True)
        elem_name = elem_of_path[tmpl_path]
        body = _build_template_body(instances, elem_name)
        tmpl_path.write_text(element_header(elem_name) + dump_yaml(body), encoding="utf-8")

    fi_path = (base / SHARED_FOLDER if has_scope else base) / ROOT_YAML
    fi_path.parent.mkdir(parents=True, exist_ok=True)
    fi_body = _build_template_file_info(file_info_root)
    fi_path.write_text(element_header(ROOT_TAG) + dump_yaml(fi_body), encoding="utf-8")
    logger.info(
        "scaffold: %d XML(s) → %d element template(s) + FileInfo",
        len(xml_paths), len(groups),
    )


def _template_path_for(
    base: Path, bare_stem: str, scope: Optional[str], has_scope: bool,
) -> Path:
    """``template/`` 下 scaffold 文件路径."""
    if not has_scope:
        return base / f"{bare_stem}.yaml"
    if scope == SHARED_FOLDER:
        return base / SHARED_FOLDER / f"{bare_stem}.yaml"
    return base / FAKE_RUNMODE_FOLDER / f"{bare_stem}.yaml"


def _build_template_body(instances: List[Any], elem_name: str) -> CommentedMap:
    """根据 element 形态分发 wrapper / 自命名 scaffold builder."""
    if elem_name == WRAPPER_TAG:
        return _build_template_wrapper_body(instances)
    return _build_template_self_named_body(instances)


def _build_template_wrapper_body(instances: List[Any]) -> CommentedMap:
    """Wrapper scaffold: ``LineNum: # @related:count(<subtag>)`` + inner row 字段 union."""
    inner_fields: List[str] = []
    seen: Set[str] = set()
    subtag = DEFAULT_CHILD_TAG
    for child in instances:
        sub_children = [c for c in child if isinstance(c.tag, str)]
        if sub_children:
            subtag = sub_children[0].tag
        for sub in sub_children:
            for k in sub.attrib:
                if k not in seen:
                    seen.add(k)
                    inner_fields.append(k)

    doc = CommentedMap()
    if inner_fields:
        seq = CommentedSeq()
        row = CommentedMap()
        for f in inner_fields:
            row[f] = None
        seq.append(row)
        doc[LINE_COUNT_ATTR] = seq
    else:
        doc[LINE_COUNT_ATTR] = None
    attach_count_anchor(doc, LINE_COUNT_ATTR, subtag)
    return doc


def _build_template_self_named_body(instances: List[Any]) -> CommentedMap:
    """自命名 scaffold: outer 字段 (除 count 锚) + inner row 字段 (如有 children) union."""
    outer_fields: List[str] = []
    seen_outer: Set[str] = set()
    inner_fields: List[str] = []
    seen_inner: Set[str] = set()
    has_children = False
    subtag: Optional[str] = None
    count_attr: Optional[str] = None

    for child in instances:
        sub_children = [c for c in child if isinstance(c.tag, str)]
        if sub_children:
            has_children = True
            if subtag is None:
                subtag = sub_children[0].tag
            if count_attr is None:
                try:
                    count_attr = detect_count_attr(child.attrib, len(sub_children))
                except ValueError:
                    pass
            for sub in sub_children:
                for k in sub.attrib:
                    if k not in seen_inner:
                        seen_inner.add(k)
                        inner_fields.append(k)
        for k in child.attrib:
            if k not in seen_outer:
                seen_outer.add(k)
                outer_fields.append(k)

    doc = CommentedMap()
    for f in outer_fields:
        if has_children and f == count_attr:
            continue
        doc[f] = None

    if has_children and count_attr is not None and subtag is not None:
        seq = CommentedSeq()
        row = CommentedMap()
        for f in inner_fields:
            row[f] = None
        seq.append(row)
        doc[count_attr] = seq
        attach_count_anchor(doc, count_attr, subtag)
    return doc


def _build_template_file_info(file_info_root: Any) -> CommentedMap:
    """FileInfo scaffold: 顶层 attribute 列表，无 children/派生字段."""
    doc = CommentedMap()
    for k in file_info_root.attrib:
        doc[k] = None
    return doc
