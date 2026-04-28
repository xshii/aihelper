"""Unpack legacy XML into yaml-tree (XML → YAML).

入口：
- ``unpack(xml_path, out_dir)`` — 单 XML
- ``unpack_many(xml_paths, out_dir)`` — 多 XML 合并（同 (element, stem) 跨 XML 必须字段完全相同）

逆向 ``ecfg.legacy.postprocess.pack``，目标：``pack(unpack(xml)) == xml`` 字节级一致。
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from lxml import etree
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarint import HexCapsInt, HexInt
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

from ecfg.legacy.const import (
    ANNOT_ELEMENT,
    ANNOT_RELATED_COUNT,
    ANNOT_USE,
    CHILDREN_ORDER_YAML,
    DEFAULT_CHILD_TAG,
    ELEMENT_SELF,
    HEX_BASE,
    HEX_PREFIX_LEN,
    HEX_RE,
    INT_RE,
    KEY_VAL_SEP_LEN,
    LINE_COUNT_ATTR,
    ROOT_TAG,
    ROOT_YAML,
    RUNMODE_ATTR,
    RUNMODE_ITEM_TAG,
    RUNMODE_TBL_TAG,
    RUNMODE_VALUE_ATTR,
    SHARED_FOLDER,
    TEMPLATE_FOLDER,
    WRAPPER_TAG,
    XML_ERR_TRUNC_LEN,
    YAML_INDENT_MAPPING,
    YAML_INDENT_OFFSET,
    YAML_INDENT_SEQUENCE,
    YAML_LINE_WIDTH,
    strip_variant,
)

logger = logging.getLogger(__name__)

_YAML_RT = YAML(typ="rt")
# 紧凑序列：``- `` 与父 key 同列，list item 内嵌 mapping 字段缩进 2
_YAML_RT.indent(
    mapping=YAML_INDENT_MAPPING,
    sequence=YAML_INDENT_SEQUENCE,
    offset=YAML_INDENT_OFFSET,
)
_YAML_RT.preserve_quotes = True
_YAML_RT.width = YAML_LINE_WIDTH


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

    file_info_root, children = _collect_and_dedup(xml_paths)
    has_scope = any(c.tag == RUNMODE_TBL_TAG for c in children)
    xref = _build_runmode_xref(children) if has_scope else {}

    classifications: List[Tuple[int, Any, str, str, Optional[str]]] = []
    stem_folders: Dict[str, Set[Optional[str]]] = {}
    for idx, child in enumerate(children):
        elem_name, stem = _classify(child)
        scope_folder = _scope_for(child, elem_name, stem, xref, has_scope)
        classifications.append((idx, child, elem_name, stem, scope_folder))
        stem_folders.setdefault(stem, set()).add(scope_folder)

    file_info_dir = out_dir / SHARED_FOLDER if has_scope else out_dir
    file_info_dir.mkdir(parents=True, exist_ok=True)
    _write_file_info(file_info_dir / ROOT_YAML, file_info_root)

    instances: List[Tuple[int, str, str, Optional[str]]] = []
    for idx, child, elem_name, stem, scope_folder in classifications:
        dest_dir = (out_dir / scope_folder) if scope_folder else out_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        _write_element_yaml(
            dest_dir / f"{stem}.yaml", child, elem_name, stem,
            scope_folder, stem_folders,
        )
        instances.append((idx, elem_name, stem, scope_folder))

    _write_children_order(
        out_dir / TEMPLATE_FOLDER / CHILDREN_ORDER_YAML, instances,
    )
    logger.info(
        "unpack: %d XML(s) → %d top-level children", len(xml_paths), len(children),
    )


def _collect_and_dedup(xml_paths: List[Path]) -> Tuple[Any, List[Any]]:
    """解析所有 XML，合并 children 并幂等去重；返回 (FileInfo root, children list).

    身份键：wrapper = ``(ResTbl, stem)``；自命名带 RunMode = ``(tag, RunMode-value)``；
    其他多实例 flat = 结构指纹（全内容匹配）。同 key 异内容 → raise。
    """
    file_info_attrs: Optional[Dict[str, str]] = None
    file_info_root: Any = None
    seen: Dict[Tuple, Tuple] = {}  # identity → structural fingerprint
    children: List[Any] = []

    for xml_path in xml_paths:
        xml_path = Path(xml_path).resolve()
        logger.info("unpack: 解析 %s", xml_path)
        tree = etree.parse(str(xml_path))
        root = tree.getroot()
        if root.tag != ROOT_TAG:
            raise ValueError(f"{xml_path}: root must be <{ROOT_TAG}>, got <{root.tag}>")

        attrs = dict(root.attrib)
        if file_info_attrs is None:
            file_info_attrs, file_info_root = attrs, root
        elif file_info_attrs != attrs:
            raise ValueError(
                f"{xml_path}: FileInfo 属性与首份 XML 冲突 — {file_info_attrs} vs {attrs}"
            )

        for child in root:
            if not isinstance(child.tag, str):
                continue
            iden = _multi_xml_identity(child)
            fingerprint = _structural_fingerprint(child)
            prior = seen.get(iden)
            if prior is not None:
                if prior != fingerprint:
                    raise ValueError(
                        f"{xml_path}: identity {iden} 在多份 XML 中字段不同（非幂等去重）"
                    )
                continue
            seen[iden] = fingerprint
            children.append(child)
    return file_info_root, children


def _multi_xml_identity(child: Any) -> Tuple:
    """跨 XML 合并的身份键：wrapper / 带 RunMode 的自命名 → 显式 key；其他 → 结构指纹."""
    elem_name, stem = _classify(child)
    if elem_name == WRAPPER_TAG:
        return (WRAPPER_TAG, stem)
    if RUNMODE_ATTR in child.attrib:
        return (child.tag, RUNMODE_ATTR, child.attrib[RUNMODE_ATTR])
    if RUNMODE_VALUE_ATTR in child.attrib:
        return (child.tag, RUNMODE_VALUE_ATTR, child.attrib[RUNMODE_VALUE_ATTR])
    return _structural_fingerprint(child)


def _structural_fingerprint(child: Any) -> Tuple:
    """递归 (tag, sorted_attrib_items, child_fingerprints) — hashable 且忽略 text/tail 空白."""
    return (
        child.tag,
        tuple(sorted(child.attrib.items())),
        tuple(_structural_fingerprint(c) for c in child if isinstance(c.tag, str)),
    )


def _build_runmode_xref(children: List[Any]) -> Dict[str, Set[str]]:
    """扫所有 ``<RunModeTbl>`` 的 ``<RunModeItem X="Y"/>`` 子项，建 ``Y → {RunMode}`` 映射."""
    xref: Dict[str, Set[str]] = {}
    for c in children:
        if c.tag != RUNMODE_TBL_TAG:
            continue
        run_mode = c.get(RUNMODE_ATTR)
        if run_mode is None:
            continue
        for item in c:
            if item.tag != RUNMODE_ITEM_TAG:
                continue
            for value in item.attrib.values():
                xref.setdefault(value, set()).add(run_mode)
    return xref


def _classify(child: Any) -> Tuple[str, str]:
    """``(element_name, stem)``：wrapper ``<ResTbl X="Y" .../>`` → (ResTbl, Y)；自命名 → (X, X)."""
    if child.tag == WRAPPER_TAG:
        for k, v in child.attrib.items():
            if k != LINE_COUNT_ATTR:
                return (WRAPPER_TAG, v)
        raise ValueError(
            f"<{WRAPPER_TAG}> 缺 type-attr: {etree.tostring(child)[:XML_ERR_TRUNC_LEN]!r}"
        )
    return (child.tag, child.tag)


def _scope_for(
    child: Any, elem_name: str, stem: str,
    xref: Dict[str, Set[str]], has_scope: bool,
) -> Optional[str]:
    """根据 child 的 ``RunMode``/``RunModeValue`` 直接绑定；ResTbl wrapper 走 xref 反查."""
    if not has_scope:
        return None
    if RUNMODE_ATTR in child.attrib:
        return child.attrib[RUNMODE_ATTR]
    if RUNMODE_VALUE_ATTR in child.attrib:
        return child.attrib[RUNMODE_VALUE_ATTR]
    if elem_name == WRAPPER_TAG:
        runmodes = xref.get(stem, set())
        if len(runmodes) == 1:
            return next(iter(runmodes))
    return SHARED_FOLDER


def _write_file_info(path: Path, root: Any) -> None:
    """FileInfo.yaml — flat mapping，无 ``@element`` 头（文档根例外）."""
    doc = CommentedMap()
    for k, v in root.attrib.items():
        doc[k] = _attrib_to_yaml_value(v)
    path.write_text(_dump_yaml(doc), encoding="utf-8")


def _write_element_yaml(
    path: Path, child: Any, elem_name: str, stem: str,
    current_folder: Optional[str], stem_folders: Dict[str, Set[Optional[str]]],
) -> None:
    """element data yaml：首行 ``@element:<X>`` + 数据。跨目录 ref 自动加 ``@use:<rel-path>``."""
    bare_stem = strip_variant(stem)
    if elem_name == WRAPPER_TAG:
        body = _build_wrapper_body(child, current_folder, stem_folders)
        header = f"# {ANNOT_ELEMENT}{elem_name}\n"
    elif elem_name == bare_stem:
        body = _build_self_named_body(child, current_folder, stem_folders)
        header = f"# {ANNOT_ELEMENT}{ELEMENT_SELF}\n"
    else:
        body = _build_self_named_body(child, current_folder, stem_folders)
        header = f"# {ANNOT_ELEMENT}{elem_name}\n"
    path.write_text(header + _dump_yaml(body), encoding="utf-8")


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
    doc.yaml_add_eol_comment(
        f"{ANNOT_RELATED_COUNT}({subtag})", LINE_COUNT_ATTR,
        column=len(LINE_COUNT_ATTR) + KEY_VAL_SEP_LEN,
    )
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

    count_attr = _detect_count_attr(child.attrib, len(sub_children))
    for k, v in child.attrib.items():
        if k != count_attr:
            doc[k] = _attrib_to_yaml_value(v)

    doc[count_attr] = _build_children_seq(sub_children, current_folder, stem_folders)
    doc.yaml_add_eol_comment(
        f"{ANNOT_RELATED_COUNT}({sub_children[0].tag})", count_attr,
        column=len(count_attr) + KEY_VAL_SEP_LEN,
    )
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


def _detect_count_attr(attrib: Dict[str, str], n_children: int) -> str:
    """heuristic：找值等于 ``n_children`` 的 attribute 作 count 锚；多候选 → WARNING + 选首个."""
    candidates = [k for k, v in attrib.items() if INT_RE.match(v) and int(v) == n_children]
    if not candidates:
        raise ValueError(
            f"无法识别 count 锚字段（attrib={dict(attrib)}, len(children)={n_children}）"
        )
    if len(candidates) > 1:
        logger.warning(
            "count 锚字段歧义：attrs %s 都 == %d；选首个 %r（attrib=%s）",
            candidates, n_children, candidates[0], dict(attrib),
        )
    return candidates[0]


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
    """生成 ``_children_order.yaml``：仅 element-class catch-all + ``<element>:<stem>`` 特例.

    设计契约：template 描述**类约束**，不再枚举 stem。
    - 同 element 跨 XML 出现 N 次（被其他 element 隔开 N 个 block）：
      仅最后一个 block 可用 catch-all ``- <Element>``，前面 block 用 ``- <E>:<stem>`` 特例
    - catch-all 要求 block 内 ``(stem, folder)`` 字母序 == XML idx 序；不满足则降级为特例
    - 同 element 类内字母序为协议契约 — XML 必须按相同顺序声明同 element 实例
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    seq = CommentedSeq()
    blocks = _group_consecutive_by_element(instances)
    last_block_idx = {elem: bi for bi, (elem, _) in enumerate(blocks)}

    for bi, (elem, block) in enumerate(blocks):
        is_trailing = bi == last_block_idx[elem]
        if is_trailing and _alphabetic_matches_xml(block):
            seq.append(elem)
        else:
            for _, _, stem, _ in block:
                seq.append(f"{elem}:{stem}")

    text = "# FileInfo children emit order\n" + _dump_yaml(seq)
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


def _dump_yaml(doc: Any) -> str:
    buf = io.StringIO()
    _YAML_RT.dump(doc, buf)
    return buf.getvalue()
