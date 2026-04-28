"""Unpack legacy XML into yaml-tree (XML → YAML).

入口：
- ``unpack(xml_path, out_dir)`` — 单 XML
- ``unpack_many(xml_paths, out_dir)`` — 多 XML 合并（同 (element, stem) 跨 XML 必须字段完全相同）

逆向 ``ecfg.legacy.postprocess.pack``，目标：``pack(unpack(xml)) == xml`` 字节级一致。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarint import HexCapsInt, HexInt
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

from ecfg.legacy._parse import (
    build_runmode_xref,
    classify,
    collect_and_dedup,
    detect_count_attr,
    scope_for,
)
from ecfg.legacy._yaml import attach_count_anchor, dump_yaml, element_header
from ecfg.legacy.const import (
    ANNOT_USE,
    CHILDREN_ORDER_YAML,
    DEFAULT_CHILD_TAG,
    ELEMENT_SELF,
    HEX_BASE,
    HEX_PREFIX_LEN,
    HEX_RE,
    INT_RE,
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


def unpack(xml_path: Path, out_dir: Path) -> None:
    """单 XML 入口；委托给 ``unpack_many``."""
    unpack_many([xml_path], out_dir)


def unpack_many(xml_paths: List[Path], out_dir: Path) -> None:
    """合并多份 XML 写出 yaml 树。

    幂等去重规则：同 ``(elem_name, stem)`` 跨 XML 出现 → 必须结构完全相同；任一字段不同 → raise。
    FileInfo 属性必须跨 XML 完全一致。
    """
    if not xml_paths:
        raise ValueError("xml_paths 不能为空")
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    file_info_root, children = collect_and_dedup(xml_paths)
    has_scope = any(c.tag == RUNMODE_TBL_TAG for c in children)
    xref = build_runmode_xref(children) if has_scope else {}

    classifications: List[Tuple[int, Any, str, str, Optional[str]]] = []
    stem_folders: Dict[str, Set[Optional[str]]] = {}
    for idx, child in enumerate(children):
        elem_name, stem = classify(child)
        scope_folder = scope_for(child, elem_name, stem, xref, has_scope)
        classifications.append((idx, child, elem_name, stem, scope_folder))
        stem_folders.setdefault(stem, set()).add(scope_folder)

    file_info_dir = out_dir / SHARED_FOLDER if has_scope else out_dir
    file_info_dir.mkdir(parents=True, exist_ok=True)
    _write_file_info(file_info_dir / ROOT_YAML, file_info_root)

    instances: List[Tuple[int, str, str, Optional[str]]] = []
    file_groups: Dict[Path, List[Tuple[Any, str, str, Optional[str]]]] = {}
    for idx, child, elem_name, stem, scope_folder in classifications:
        dest_dir = (out_dir / scope_folder) if scope_folder else out_dir
        dest_path = dest_dir / f"{stem}.yaml"
        file_groups.setdefault(dest_path, []).append(
            (child, elem_name, stem, scope_folder),
        )
        instances.append((idx, elem_name, stem, scope_folder))

    # 同 (file_path) 多 instance（如多 flat ``<CapacityRunModeMapTbl/>`` 同 scope）→
    # 合并为 list-of-mappings 主体（R1）；单 instance 走扁平 mapping（R6）
    for dest_path, group in file_groups.items():
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if len(group) == 1:
            child, elem_name, stem, scope_folder = group[0]
            _write_element_yaml(
                dest_path, child, elem_name, stem, scope_folder, stem_folders,
            )
        else:
            _write_multi_instance_flat(dest_path, group, stem_folders)

    _write_children_order(
        out_dir / TEMPLATE_FOLDER / CHILDREN_ORDER_YAML, instances,
    )
    logger.info(
        "unpack: %d XML(s) → %d top-level children", len(xml_paths), len(children),
    )


def _write_multi_instance_flat(
    path: Path,
    group: List[Tuple[Any, str, str, Optional[str]]],
    stem_folders: Dict[str, Set[Optional[str]]],
) -> None:
    """同 (file path) 多 flat instance（R1）→ 单文件首行 ``# @element`` + list-of-mappings 主体.

    所有 instance 共享 ``elem_name`` 和 ``stem``（同名 flat 在同 scope 才会同 path）。
    每个 instance 走 ``_build_self_named_body`` 拿 mapping，aggregate 成 ``CommentedSeq``。
    """
    first_child, elem_name, stem, scope_folder = group[0]
    bare_stem = strip_variant(stem)
    if elem_name == WRAPPER_TAG:
        # wrapper 多实例同 path 不应发生（每个 wrapper stem 唯一），但留兜底
        raise ValueError(
            f"{path}: wrapper 多实例同名同 scope，应不可能；attrs={dict(first_child.attrib)}"
        )
    header = element_header(ELEMENT_SELF if elem_name == bare_stem else elem_name)
    seq = CommentedSeq()
    for child, _, _, _ in group:
        seq.append(_build_self_named_body(child, scope_folder, stem_folders))
    path.write_text(header + dump_yaml(seq), encoding="utf-8")


def _write_file_info(path: Path, root: Any) -> None:
    """FileInfo.yaml — 首行 ``# @element:FileInfo`` + 扁平 attribute mapping."""
    doc = CommentedMap()
    for k, v in root.attrib.items():
        doc[k] = _attrib_to_yaml_value(v)
    path.write_text(element_header(ROOT_TAG) + dump_yaml(doc), encoding="utf-8")


def _write_element_yaml(
    path: Path, child: Any, elem_name: str, stem: str,
    current_folder: Optional[str], stem_folders: Dict[str, Set[Optional[str]]],
) -> None:
    """element data yaml：首行 ``@element:<X>`` + 数据。跨目录 ref 自动加 ``@use:<rel-path>``."""
    bare_stem = strip_variant(stem)
    if elem_name == WRAPPER_TAG:
        body = _build_wrapper_body(child, current_folder, stem_folders)
    elif elem_name == bare_stem:
        body = _build_self_named_body(child, current_folder, stem_folders)
    else:
        body = _build_self_named_body(child, current_folder, stem_folders)
    header = element_header(ELEMENT_SELF if elem_name == bare_stem else elem_name)
    path.write_text(header + dump_yaml(body), encoding="utf-8")


def _build_wrapper_body(
    child: Any, current_folder: Optional[str], stem_folders: Dict[str, Set[Optional[str]]],
) -> CommentedMap:
    """ResTbl wrapper：跳过 type-attr，LineNum 作为 ``@related:count(<subtag>)`` 派生 host."""
    sub_children = [c for c in child if isinstance(c.tag, str)]
    subtag = sub_children[0].tag if sub_children else DEFAULT_CHILD_TAG

    doc = CommentedMap()
    if sub_children:
        doc[LINE_COUNT_ATTR] = _build_children_seq(sub_children, current_folder, stem_folders)
    else:
        doc[LINE_COUNT_ATTR] = None
    attach_count_anchor(doc, LINE_COUNT_ATTR, subtag)
    return doc


def _build_self_named_body(
    child: Any, current_folder: Optional[str], stem_folders: Dict[str, Set[Optional[str]]],
) -> CommentedMap:
    """自命名：扁平 attribute；如有 children，值 == len(children) 的字段作 count 锚."""
    sub_children = [c for c in child if isinstance(c.tag, str)]
    doc = CommentedMap()
    if not sub_children:
        for k, v in child.attrib.items():
            doc[k] = _attrib_to_yaml_value(v)
        return doc

    count_attr = detect_count_attr(child.attrib, len(sub_children))
    for k, v in child.attrib.items():
        if k != count_attr:
            doc[k] = _attrib_to_yaml_value(v)

    doc[count_attr] = _build_children_seq(sub_children, current_folder, stem_folders)
    attach_count_anchor(doc, count_attr, sub_children[0].tag)
    return doc


def _build_children_seq(
    sub_children: List[Any],
    current_folder: Optional[str],
    stem_folders: Dict[str, Set[Optional[str]]],
) -> CommentedSeq:
    """list-of-mappings：每个 child 的 attribute set → 一个 row；跨目录 ref attach ``@use``."""
    seq = CommentedSeq()
    for sub in sub_children:
        row = CommentedMap()
        for k, v in sub.attrib.items():
            row[k] = _attrib_to_yaml_value(v)
        _attach_use_comments(row, sub.attrib, current_folder, stem_folders)
        seq.append(row)
    return seq


def _attach_use_comments(
    row: CommentedMap,
    attrib: Dict[str, str],
    current_folder: Optional[str],
    stem_folders: Dict[str, Set[Optional[str]]],
) -> None:
    """row 内 value 是已知 stem 且位于不同 folder 的字段，加 ``# @use:<rel>`` 行尾注释。

    歧义处理：同一 stem 同时存在于多个 folder（例：``RunModeTbl`` 在每个 RunMode/ 下）。
    - ref 出自其中一个 folder → 视为同 folder 命中，不加 @use
    - ref 出自其他 folder → 目标不唯一，WARNING + 跳过（不猜路径）
    """
    for k, v in attrib.items():
        folders = stem_folders.get(v)
        if folders is None or current_folder in folders:
            continue
        if len(folders) > 1:
            logger.warning(
                "%s=%r 跨多个 folder %s，无法确定 @use 路径（current=%r）",
                k, v, sorted(str(f) for f in folders), current_folder,
            )
            continue
        target = next(iter(folders))
        row.yaml_add_eol_comment(
            f"{ANNOT_USE}{_rel_use_path(current_folder, target, v)}", k,
        )


def _rel_use_path(current: Optional[str], target: Optional[str], stem: str) -> str:
    """``@use:`` 相对路径：``..`` 跳出 current，``<target>/`` 进 target，文件名 ``<stem>.yaml``."""
    parts: List[str] = []
    if current is not None:
        parts.append("..")
    if target is not None:
        parts.append(target)
    parts.append(f"{stem}.yaml")
    return "/".join(parts)


def _attrib_to_yaml_value(s: str) -> Any:
    """XML attribute string → ruamel rt 友好 Python 值，保留 hex 宽度+大小写。"""
    if s == "":
        return DoubleQuotedScalarString("")
    if HEX_RE.match(s):
        digits = s[HEX_PREFIX_LEN:]
        val = int(s, HEX_BASE)
        is_caps = any(c.isupper() for c in digits)
        actual_width = len(digits)
        width = actual_width if actual_width > len(f"{val:x}") else None
        cls = HexCapsInt if is_caps else HexInt
        return cls(val, width=width) if width else cls(val)
    if INT_RE.match(s):
        return int(s)
    return DoubleQuotedScalarString(s)


def _write_children_order(
    path: Path,
    instances: List[Tuple[int, str, str, Optional[str]]],
) -> None:
    """生成 ``_children_order.yaml``：顶层 ``{FileInfo: [<children>]}`` 嵌套 mapping.

    children list 描述**类约束**，仅两种 entry 形式：
    - ``- <Element>`` element-class catch-all：匹配该 element 的所有未消费文件
    - ``- <element>:<stem>`` 特例：精确 pin 单个 instance

    同 element 跨 XML 出现 N 次（被其他 element 隔开 N 个 block）：仅最后一个 block 可用
    catch-all，前面 block 用特例。catch-all 要求 block 内 ``(stem, folder)`` 字母序 ==
    XML idx 序；不满足则降级为特例。同 element 类内字母序为协议契约 — XML 必须按相同顺序
    声明同 element 实例。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    children = CommentedSeq()
    blocks = _group_consecutive_by_element(instances)
    last_block_idx = {elem: bi for bi, (elem, _) in enumerate(blocks)}

    for bi, (elem, block) in enumerate(blocks):
        is_trailing = bi == last_block_idx[elem]
        if is_trailing and _alphabetic_matches_xml(block):
            children.append(elem)
        else:
            for _, _, stem, _ in block:
                children.append(f"{elem}:{stem}")

    # 嵌套形态：top-level mapping ``FileInfo: <list>`` — yaml 结构表达
    # "FileInfo 是根，children 在它下面"
    doc = CommentedMap()
    doc[ROOT_TAG] = children
    text = "# Top-level emit order — FileInfo (root) → list of child entries\n" + dump_yaml(doc)
    path.write_text(text, encoding="utf-8")


def _group_consecutive_by_element(
    instances: List[Tuple[int, str, str, Optional[str]]],
) -> List[Tuple[str, List[Tuple[int, str, str, Optional[str]]]]]:
    """把 instances 按 XML 出现顺序切成「连续同 element」block 序列."""
    blocks: List[Tuple[str, List[Tuple[int, str, str, Optional[str]]]]] = []
    current_elem: Optional[str] = None
    current_block: List[Tuple[int, str, str, Optional[str]]] = []
    for inst in instances:
        elem = inst[1]
        if elem != current_elem:
            if current_block and current_elem is not None:
                blocks.append((current_elem, current_block))
            current_elem, current_block = elem, [inst]
        else:
            current_block.append(inst)
    if current_block and current_elem is not None:
        blocks.append((current_elem, current_block))
    return blocks


def _alphabetic_matches_xml(
    block: List[Tuple[int, str, str, Optional[str]]],
) -> bool:
    """block 内 ``(stem, scope_folder)`` 字母序是否与 XML idx 序一致.

    与 ``postprocess._consume_class_entry`` 的 ``(stem, full path)`` 等价（folder 决定 path 前缀）。
    """
    by_alpha = sorted(block, key=lambda t: (t[2], t[3] or ""))
    by_xml = sorted(block, key=lambda t: t[0])
    return by_alpha == by_xml


