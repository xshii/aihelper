"""Pack legacy yaml-tree fixture into byte-stable XML.

实现 prompts/skill-postprocess.md 描述的 post-process skill。
入口：``pack(fixture_dir: Path) -> str``。

约定（参考 docs/yaml-schema.md）：
- 文档根 = ``FileInfo.yaml``（在 fixture root 或 ``shared/``）
- emit 顺序由 ``template/_children_order.yaml`` 决定
- ``# @element:<self>`` → element 名 = stem 去 variant；显式名 → 字面
- wrapper 形态（X != <self>）：type-attr name = stem 去 variant；value = stem 全名
- 派生字段 ``KEY: # @related:count(<Child>)``
  → emit 时 KEY = ``len(list)``，list items 平级挂为 children
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from lxml import etree
from ruamel.yaml.scalarint import HexCapsInt, HexInt

from ecfg.legacy._yaml import YAML_RT, format_hex
from ecfg.legacy.const import (
    ANNOT_ELEMENT,
    ANNOT_RELATED_COUNT,
    CHILDREN_ORDER_YAML,
    ELEMENT_SELF,
    LXML_TO_LEGACY_INDENT_RATIO,
    ROOT_TAG,
    ROOT_YAML,
    SHARED_FOLDER,
    TEMPLATE_FOLDER,
    strip_variant,
)
from ecfg.schema._comments import trailing_comment

logger = logging.getLogger(__name__)

_ELEMENT_HEADER = re.compile(rf"^#\s*{re.escape(ANNOT_ELEMENT)}(\S+)\s*$")
_RELATED_COUNT = re.compile(rf"{re.escape(ANNOT_RELATED_COUNT)}\(([^)]+)\)")


def pack(fixture_dir: Path) -> str:
    """把 yaml-tree fixture 拼装为 legacy XML 字符串.

    ``_children_order.yaml`` 顶层是 ``{FileInfo: [<children>]}`` 嵌套结构 — yaml
    自身表达"FileInfo 是根，list 是其 children 的 emit 顺序"。
    """
    fixture_dir = Path(fixture_dir).resolve()
    logger.info("pack: fixture=%s", fixture_dir)

    children_order = _load_children_order(fixture_dir)
    file_info_path = _find_file_info(fixture_dir)
    logger.debug("pack: FileInfo=%s, children_order=%s", file_info_path.name, children_order)

    file_info_data = _load_yaml(file_info_path)
    root = etree.Element(ROOT_TAG)
    for key, value in file_info_data.items():
        root.set(key, _format_scalar(value))

    ordered = _ordered_children(fixture_dir, children_order)
    _warn_on_orphan_files(fixture_dir, ordered)

    emit_count = 0
    for child_path in ordered:
        child_data = _load_yaml(child_path)
        if isinstance(child_data, list):
            for item in child_data:
                _emit_element(root, child_path, item)
                emit_count += 1
        else:
            _emit_element(root, child_path, child_data)
            emit_count += 1
    logger.info("pack: emitted %d top-level elements", emit_count)

    body = etree.tostring(root, pretty_print=True, encoding="unicode")
    body = _reindent_to_4_spaces(body)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body


def _warn_on_orphan_files(fixture_dir: Path, ordered: list[Path]) -> None:
    """fixture 里有但 ``_children_order`` 没列的 element yaml → WARNING（避免静默丢失）."""
    expected = set(ordered)
    all_data = {
        p for p in fixture_dir.rglob("*.yaml")
        if p.name != ROOT_YAML
        and not p.name.startswith("_")
        and TEMPLATE_FOLDER not in p.parts
    }
    orphans = sorted(all_data - expected)
    for orphan in orphans:
        logger.warning(
            "pack: %s 不在 %s 任何 class 下，将被丢弃",
            orphan.relative_to(fixture_dir), CHILDREN_ORDER_YAML,
        )


def _find_file_info(fixture_dir: Path) -> Path:
    for candidate in (
        fixture_dir / SHARED_FOLDER / ROOT_YAML,
        fixture_dir / ROOT_YAML,
    ):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"{ROOT_YAML} not found in {fixture_dir} or its {SHARED_FOLDER}/"
    )


def _load_yaml(path: Path) -> Any:
    return YAML_RT.load(path.read_text(encoding="utf-8"))


def _load_children_order(fixture_dir: Path) -> list[str]:
    """读 ``_children_order.yaml`` — 顶层 ``{FileInfo: [<children>]}``，返回 children list."""
    meta = fixture_dir / TEMPLATE_FOLDER / CHILDREN_ORDER_YAML
    if not meta.is_file():
        raise FileNotFoundError(f"Missing {meta}")
    loaded = YAML_RT.load(meta.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict) or ROOT_TAG not in loaded:
        raise ValueError(
            f"{meta}: 顶层必须是 ``{{ {ROOT_TAG}: [<children>] }}`` 嵌套结构；"
            f"实际：{type(loaded).__name__}"
        )
    return [str(x) for x in loaded[ROOT_TAG]]


def _ordered_children(fixture_dir: Path, order: list[str]) -> list[Path]:
    """收集所有 element data yaml（排除 FileInfo / template/ / 下划线 meta）。

    每条 entry 二选一：
    - ``<class>``（无 ``:``）：class 兜底匹配，stem == class 或 stem 以 ``class_`` 开头。
      class 内多 instance 排序键 ``(element 名, stem, 全路径)``。
    - ``<element>:<stem>``（有 ``:``）：特例精确匹配，pin 单个 instance 到此位置。

    匹配按 ``order`` 顺序贪心；每文件最多匹配一次。文件夹层级（shared/ vs scope/）
    **不参与**排序——属于存储约定，非数据语义。
    """
    all_data = [
        p for p in fixture_dir.rglob("*.yaml")
        if p.name != ROOT_YAML
        and not p.name.startswith("_")
        and TEMPLATE_FOLDER not in p.parts
    ]

    result: list[Path] = []
    used: set[Path] = set()
    for entry in order:
        if ":" in entry:
            consumed = _consume_specific_entry(entry, all_data, used)
        else:
            consumed = _consume_class_entry(entry, all_data, used)
        if not consumed:
            logger.warning(
                "%s 列了 %r 但 fixture 找不到匹配文件", CHILDREN_ORDER_YAML, entry,
            )
        result.extend(consumed)
        used.update(consumed)
    return result


def _consume_specific_entry(
    entry: str, all_data: list[Path], used: set[Path],
) -> list[Path]:
    """``<element>:<stem>`` 特例：精确匹配 (resolved element name, stem)."""
    elem_target, stem_target = entry.split(":", 1)
    for p in all_data:
        if p in used:
            continue
        if p.stem == stem_target and _resolve_element_name(p) == elem_target:
            return [p]
    return []


def _consume_class_entry(
    entry: str, all_data: list[Path], used: set[Path],
) -> list[Path]:
    """``<entry>`` element-class 匹配：``resolved element name == entry`` 的所有未消费文件。

    设计契约：template 只描述 **element 类约束**；同 element 类内 stem 字母序为协议契约
    （XML 必须按相同顺序声明），否则 round-trip 失败。无回退 stem-match。

    排序键 ``(stem, full path)``（element 已固定为 entry，path 为同 stem 跨 folder 的 tiebreak）。
    """
    matches: list[tuple[str, str, Path]] = []
    for p in all_data:
        if p in used:
            continue
        if _resolve_element_name(p) == entry:
            matches.append((p.stem, str(p), p))
    matches.sort()
    return [p for _, _, p in matches]


def _resolve_element_name(yaml_path: Path) -> str:
    first = yaml_path.read_text(encoding="utf-8").splitlines()[0]
    m = _ELEMENT_HEADER.match(first.strip())
    if not m:
        raise ValueError(f"{yaml_path}: 缺少 # {ANNOT_ELEMENT}<X> 首行")
    val = m.group(1)
    if val == ELEMENT_SELF:
        return strip_variant(yaml_path.stem)
    return val


def _emit_element(parent: etree._Element, yaml_path: Path, data: Any) -> None:
    """在 parent 下创建一个 XML element，对应 yaml_path 的一份 data."""
    elem_name = _resolve_element_name(yaml_path)
    stem = yaml_path.stem
    bare_stem = strip_variant(stem)

    elem = etree.SubElement(parent, elem_name)
    if elem_name != bare_stem:
        elem.set(bare_stem, stem)  # wrapper type-attr

    derived_children = _scan_derived_count(data)
    for key, value in data.items():
        if key in derived_children:
            children = list(value) if isinstance(value, list) else []
            _emit_derived_children(elem, key, derived_children[key], children)
        else:
            elem.set(key, _format_scalar(value))


def _emit_derived_children(
    parent: etree._Element, count_key: str, child_name: str, children: list,
) -> None:
    """派生字段：``count_key`` 设为 ``len(children)``，items 平级 emit 为 ``<child_name .../>``."""
    parent.set(count_key, str(len(children)))
    for item in children:
        child = etree.SubElement(parent, child_name)
        for k, v in item.items():
            child.set(k, _format_scalar(v))


def _scan_derived_count(doc: Any) -> dict[str, str]:
    """从 ruamel CommentedMap 的尾随注释里抽出 @related:count(X) → {key: child_name}."""
    result: dict[str, str] = {}
    if not hasattr(doc, "ca"):
        return result
    for key in doc:
        comment = trailing_comment(doc, key)
        if not comment:
            continue
        m = _RELATED_COUNT.search(comment)
        if m:
            result[key] = m.group(1).strip()
    return result


def _format_scalar(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (HexCapsInt, HexInt)):
        return format_hex(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    return str(v)


def _reindent_to_4_spaces(xml_text: str) -> str:
    """lxml ``pretty_print=True`` 用 2 空格缩进；legacy XML 风格为 4 空格——逐行倍增前导空格."""
    out = []
    for line in xml_text.split("\n"):
        stripped = line.lstrip(" ")
        leading = len(line) - len(stripped)
        out.append(" " * (leading * LXML_TO_LEGACY_INDENT_RATIO) + stripped)
    return "\n".join(out)
