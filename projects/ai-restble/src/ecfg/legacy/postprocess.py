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

import re
from pathlib import Path
from typing import Any

from lxml import etree
from ruamel.yaml import YAML
from ruamel.yaml.scalarint import HexCapsInt, HexInt

from ecfg.schema._comments import trailing_comment

_YAML_RT = YAML(typ="rt")

_ELEMENT_HEADER = re.compile(r"^#\s*@element:(\S+)\s*$")
_RELATED_COUNT = re.compile(r"@related:count\(([^)]+)\)")
_VARIANT_SUFFIX = re.compile(r"^(.+?)_(0[xX][0-9A-Fa-f]+)$")


def pack(fixture_dir: Path) -> str:
    """把 yaml-tree fixture 拼装为 legacy XML 字符串（无 XML 声明，调用方自加）."""
    fixture_dir = Path(fixture_dir).resolve()
    file_info_path = _find_file_info(fixture_dir)
    children_order = _load_children_order(fixture_dir)

    file_info_data = _load_yaml(file_info_path)
    root = etree.Element("FileInfo")
    for key, value in file_info_data.items():
        root.set(key, _format_scalar(value))

    for child_path in _ordered_children(fixture_dir, children_order):
        child_data = _load_yaml(child_path)
        if isinstance(child_data, list):
            for item in child_data:
                _emit_element(root, child_path, item)
        else:
            _emit_element(root, child_path, child_data)

    body = etree.tostring(root, pretty_print=True, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body


def _find_file_info(fixture_dir: Path) -> Path:
    for candidate in (
        fixture_dir / "shared" / "FileInfo.yaml",
        fixture_dir / "FileInfo.yaml",
    ):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"FileInfo.yaml not found in {fixture_dir} or its shared/"
    )


def _load_yaml(path: Path) -> Any:
    return _YAML_RT.load(path.read_text(encoding="utf-8"))


def _load_children_order(fixture_dir: Path) -> list[str]:
    meta = fixture_dir / "template" / "_children_order.yaml"
    if not meta.is_file():
        raise FileNotFoundError(f"Missing {meta}")
    loaded = _YAML_RT.load(meta.read_text(encoding="utf-8"))
    return [str(x) for x in loaded]


def _ordered_children(fixture_dir: Path, order: list[str]) -> list[Path]:
    """收集所有 element data yaml（排除 FileInfo / template/ / 下划线 meta）。

    排序：class（按 ``order`` 中位置）→ shared 优先 → element 名升序 → 全路径升序。
    """
    all_data = [
        p for p in fixture_dir.rglob("*.yaml")
        if p.name != "FileInfo.yaml"
        and not p.name.startswith("_")
        and "template" not in p.parts
    ]

    result: list[Path] = []
    for logical in order:
        matches: list[tuple[bool, str, str, Path]] = []
        for p in all_data:
            stem = p.stem
            if stem == logical or stem.startswith(logical + "_"):
                elem = _resolve_element_name(p)
                in_scope = "shared" not in p.parts  # shared/ 排在 scope/ 之前
                matches.append((in_scope, elem, str(p), p))
        matches.sort()
        result.extend(p for _, _, _, p in matches)
    return result


def _resolve_element_name(yaml_path: Path) -> str:
    first = yaml_path.read_text(encoding="utf-8").splitlines()[0]
    m = _ELEMENT_HEADER.match(first.strip())
    if not m:
        raise ValueError(f"{yaml_path}: 缺少 # @element:<X> 首行")
    val = m.group(1)
    if val == "<self>":
        return _strip_variant(yaml_path.stem)
    return val


def _strip_variant(stem: str) -> str:
    """去掉 _<hex> 后缀（若存在）."""
    m = _VARIANT_SUFFIX.match(stem)
    return m.group(1) if m else stem


def _emit_element(parent: etree._Element, yaml_path: Path, data: Any) -> None:
    """在 parent 下创建一个 XML element，对应 yaml_path 的一份 data."""
    elem_name = _resolve_element_name(yaml_path)
    stem = yaml_path.stem
    bare_stem = _strip_variant(stem)

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
        return _format_hex(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    return str(v)


def _format_hex(v: Any) -> str:
    """ruamel HexInt/HexCapsInt → ``0xHEX`` 字面，保留 width + 大小写."""
    width = getattr(v, "_width", None)
    case_spec = "X" if isinstance(v, HexCapsInt) else "x"
    if width:
        return f"0x{int(v):0{width}{case_spec}}"
    return f"0x{int(v):{case_spec}}"
