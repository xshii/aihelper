"""legacy/ 子包共享的 XML 协议解析 helper.

由 preprocess / scaffold 共享：分类 (wrapper vs 自命名) / scope 判定 / 多 XML 合并去重 /
RunMode 反向索引 / count 锚字段启发 / 结构指纹。

这些是协议级 helper，不在公开 API 里 — 仅 ``ecfg.legacy.*`` 内部调用。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from lxml import etree

from ecfg.legacy.const import (
    INT_RE,
    LINE_COUNT_ATTR,
    ROOT_TAG,
    RUNMODE_ATTR,
    RUNMODE_ITEM_TAG,
    RUNMODE_TBL_TAG,
    RUNMODE_VALUE_ATTR,
    SHARED_FOLDER,
    WRAPPER_TAG,
    XML_ERR_TRUNC_LEN,
)

logger = logging.getLogger(__name__)


def collect_and_dedup(xml_paths: List[Path]) -> Tuple[Any, List[Any]]:
    """解析所有 XML，合并 children 并幂等去重；返回 ``(FileInfo root, children list)``.

    身份键由 ``multi_xml_identity`` 决定：wrapper = ``(ResTbl, stem)``；
    自命名带 RunMode singleton = ``(tag, RunMode-value)``；其他多实例 flat = 结构指纹。
    同 key 异内容 → raise（非幂等去重）。FileInfo 属性必须跨 XML 完全一致。
    """
    file_info_attrs: Optional[Dict[str, str]] = None
    file_info_root: Any = None
    seen: Dict[Tuple, Tuple] = {}
    children: List[Any] = []

    for xml_path in xml_paths:
        xml_path = Path(xml_path).resolve()
        logger.info("parse: %s", xml_path)
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
            iden = multi_xml_identity(child)
            fingerprint = structural_fingerprint(child)
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


def multi_xml_identity(child: Any) -> Tuple:
    """跨 XML 合并的身份键：wrapper / 带 RunMode 的自命名 singleton → 显式 key；其他 → 结构指纹.

    注意：``RunModeValue`` 是行级 scope 引用而非唯一性键（一个 RunModeValue 下可有多个 flat
    行，由 CapacityID 等其他 attr 区分），故不参与身份键 — 走结构指纹。
    """
    elem_name, stem = classify(child)
    if elem_name == WRAPPER_TAG:
        return (WRAPPER_TAG, stem)
    if RUNMODE_ATTR in child.attrib:
        return (child.tag, RUNMODE_ATTR, child.attrib[RUNMODE_ATTR])
    return structural_fingerprint(child)


def structural_fingerprint(child: Any) -> Tuple:
    """递归 (tag, sorted_attrib_items, child_fingerprints) — hashable 且忽略 text/tail 空白."""
    return (
        child.tag,
        tuple(sorted(child.attrib.items())),
        tuple(structural_fingerprint(c) for c in child if isinstance(c.tag, str)),
    )


def build_runmode_xref(children: List[Any]) -> Dict[str, Set[str]]:
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


def classify(child: Any) -> Tuple[str, str]:
    """``(element_name, stem)``：wrapper ``<ResTbl X="Y" .../>`` → (ResTbl, Y)；自命名 → (X, X)."""
    if child.tag == WRAPPER_TAG:
        for k, v in child.attrib.items():
            if k != LINE_COUNT_ATTR:
                return (WRAPPER_TAG, v)
        raise ValueError(
            f"<{WRAPPER_TAG}> 缺 type-attr: "
            f"{etree.tostring(child)[:XML_ERR_TRUNC_LEN]!r}"
        )
    return (child.tag, child.tag)


def scope_for(
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


def detect_count_attr(attrib: Dict[str, str], n_children: int) -> str:
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
