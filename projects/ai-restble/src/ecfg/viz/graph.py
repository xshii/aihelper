"""yaml 目录 → graph JSON（节点 + 边 + referenced_by 反查表）。

协议契约：``prompts/phase2/01-graph-builder.md``。所有 JSON 字段名 / kind 枚举
集中在 ``viz/const.py``，三区域名复用 ``schema/const.py``。

当前 legacy fixture 全部无 ref 数据，输出 ``edges=[]``、``referenced_by={}``。
schema 路径含 ref 的 fixture 出现后，``_extract_edges_and_xref`` 会正常产边。
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarint import HexCapsInt, HexInt

from ecfg.legacy._yaml import YAML_RT, format_hex
from ecfg.legacy.const import (
    ANNOT_ELEMENT,
    ANNOT_RELATED_COUNT,
    CHILDREN_ORDER_YAML,
    ELEMENT_SELF,
    ROOT_TAG,
    TEMPLATE_FOLDER,
)
from ecfg.legacy.template_schema import (
    load_template_constraints,
    resolve_template_path,
)
from ecfg.schema._comments import trailing_comment
from ecfg.schema.const import REGION_ATTRIBUTE, REGION_INDEX, REGION_REF
from ecfg.viz.const import (
    DEFAULT_SCOPE,
    EDGES_KEY,
    ERR_FIELD,
    ERR_KIND,
    ERR_KIND_ENUM_MISMATCH,
    ERR_KIND_RANGE_VIOLATION,
    ERR_MESSAGE,
    ERR_REGION,
    FIELD_CONSTRAINTS,
    FIELD_NAME,
    FIELD_REGION,
    KIND_FILEINFO,
    KIND_TABLE,
    META_CATEGORIES,
    META_EDGE_COUNT,
    META_KEY,
    META_NODE_COUNT,
    META_YAML_DIR,
    NODE_CATEGORY,
    NODE_ELEMENT,
    NODE_ERROR_COUNT,
    NODE_FIELDS,
    NODE_ID,
    NODE_KIND,
    NODE_RECORDS,
    NODE_RECORDS_PREVIEW,
    NODE_SCOPE,
    NODE_TABLE_ATTRIBUTES,
    NODE_WRAPPER_TYPE,
    NODES_KEY,
    RECORD_ERRORS,
    REFERENCED_BY_KEY,
)

_REGIONS = (REGION_INDEX, REGION_ATTRIBUTE, REGION_REF)

# region public API ─────────────────────────────────────────────────────────
def build_graph(yaml_dir: Path) -> Dict[str, Any]:
    """读 ``yaml_dir`` 下所有数据 yaml，输出 graph JSON.

    返回 ``{meta, nodes, edges, referenced_by}``，前端框架无关。
    多次调用结果稳定（按文件路径字典序遍历）。
    """
    yaml_dir = Path(yaml_dir)
    if not yaml_dir.is_dir():
        raise ValueError(f"graph builder: 目录不存在 {yaml_dir}")
    nodes: List[Dict[str, Any]] = []
    categories: List[str] = []
    for yaml_path in _walk_yamls(yaml_dir):
        node = _build_node(yaml_path, yaml_dir)
        nodes.append(node)
        if node[NODE_CATEGORY] not in categories:
            categories.append(node[NODE_CATEGORY])
    # 当前 legacy fixture 全部无 ref 数据 → 边/反查表为空。schema 轨道含 ref 的
    # fixture 出现时再加 ref 投影逻辑（见 prompts/phase2/01-graph-builder.md §G3-G6）。
    edges: List[Dict[str, Any]] = []
    referenced_by: Dict[str, List[Dict[str, str]]] = {}
    return {
        META_KEY: {
            META_YAML_DIR: str(yaml_dir),
            META_CATEGORIES: categories,
            META_NODE_COUNT: len(nodes),
            META_EDGE_COUNT: len(edges),
        },
        NODES_KEY: nodes,
        EDGES_KEY: edges,
        REFERENCED_BY_KEY: referenced_by,
    }


# endregion

# region yaml walking ────────────────────────────────────────────────────────
def _walk_yamls(yaml_dir: Path) -> Iterator[Path]:
    """递归找 ``*.yaml``，排除 ``_children_order.yaml`` 和 ``template/`` 子树."""
    for p in sorted(yaml_dir.rglob("*.yaml")):
        if p.name == CHILDREN_ORDER_YAML:
            continue
        if TEMPLATE_FOLDER in p.relative_to(yaml_dir).parts:
            continue
        yield p


# endregion

# region node construction ──────────────────────────────────────────────────
def _build_node(yaml_path: Path, yaml_dir: Path) -> Dict[str, Any]:
    """单个 yaml 文件 → 一个 node dict（含完整 records + 字段集 + template 约束）."""
    rel = yaml_path.relative_to(yaml_dir)
    scope = DEFAULT_SCOPE if len(rel.parts) == 1 else rel.parts[0]
    text = yaml_path.read_text(encoding="utf-8")
    element = _parse_element_header(text)
    body = YAML_RT.load(io.StringIO(text))
    records, table_attributes = _extract_records(body)
    fields = _extract_field_set(records)
    _attach_template_constraints(fields, yaml_path, yaml_dir)
    error_count = _validate_records(records, fields)
    stem = yaml_path.stem
    node_id = stem if scope == DEFAULT_SCOPE else f"{scope}/{stem}"
    return {
        NODE_ID: node_id,
        NODE_KIND: _kind_for_node(stem),
        NODE_SCOPE: scope,
        NODE_CATEGORY: scope,
        NODE_ELEMENT: element,
        NODE_WRAPPER_TYPE: _wrapper_type(element, stem),
        NODE_FIELDS: fields,
        NODE_RECORDS_PREVIEW: len(records),
        NODE_RECORDS: records,
        NODE_TABLE_ATTRIBUTES: table_attributes,
        NODE_ERROR_COUNT: error_count,
    }


def _attach_template_constraints(
    fields: List[Dict[str, str]],
    yaml_path: Path,
    yaml_dir: Path,
) -> None:
    """查 ``template/<scope>/<E>.yaml`` 的 EOL 注解，注入到匹配的 ``fields[i]``.

    template 不存在 / 字段无注解 → 该字段不挂 ``constraints`` 键（前端见缺则
    退化为通用 text input）。in-place 修改 fields 列表。
    """
    template_path = resolve_template_path(yaml_path, yaml_dir)
    constraints = load_template_constraints(template_path)
    for f in fields:
        fc = constraints.get(f[FIELD_NAME])
        if fc is not None and not fc.is_empty():
            f[FIELD_CONSTRAINTS] = fc.to_dict()


def _validate_records(
    records: List[Dict[str, Any]],
    fields_meta: List[Dict[str, str]],
) -> int:
    """对每条 record 的每个字段值与 ``fields_meta[i].constraints`` 比对.

    违规字段挂到 ``record["errors"]`` list；返回总错误数（用于 node-level
    error_count 聚合）。in-place 修改 records，无副作用之外的依赖。
    """
    total = 0
    for r in records:
        errs = _record_errors(r, fields_meta)
        if errs:
            r[RECORD_ERRORS] = errs
            total += len(errs)
    return total


def _record_errors(
    record: Dict[str, Any],
    fields_meta: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    """单 record 的 errors 列表（按 region/field 顺序遍历，跳过 None 值）."""
    out: List[Dict[str, str]] = []
    for region in (REGION_INDEX, REGION_ATTRIBUTE, REGION_REF):
        for fname, fvalue in record.get(region, {}).items():
            if fvalue is None:
                continue
            meta = _find_field_meta(fields_meta, fname, region)
            if not meta:
                continue
            constraints = meta.get(FIELD_CONSTRAINTS)
            if not constraints:
                continue
            err = _check_value(fvalue, constraints)
            if err:
                out.append({ERR_FIELD: fname, ERR_REGION: region, **err})
    return out


def _check_value(value: Any, constraints: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """单值 vs 单字段约束 → ``{kind, message}`` 或 None.

    优先 enum 匹配（精准）后 range（数值化）；二者不冲突时取首个违规。
    """
    if "enum" in constraints:
        if str(value) not in constraints["enum"]:
            return {
                ERR_KIND: ERR_KIND_ENUM_MISMATCH,
                ERR_MESSAGE: f"{value} ∉ {{{', '.join(constraints['enum'])}}}",
            }
    if "range" in constraints:
        num = _to_numeric(value)
        if num is None:
            return None
        lo, hi = constraints["range"]
        if not (lo <= num <= hi):
            return {
                ERR_KIND: ERR_KIND_RANGE_VIOLATION,
                ERR_MESSAGE: f"{value} ∉ [{lo:g}, {hi:g}]",
            }
    return None


def _to_numeric(v: Any) -> Optional[float]:
    """value → float（含 ``0xHEX`` 字面解析）；不可数值化 → None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        try:
            if s[:2].lower() == "0x":
                return float(int(s, 16))
            return float(s)
        except (ValueError, IndexError):
            return None
    return None


def _find_field_meta(
    fields_meta: List[Dict[str, str]],
    name: str,
    region: str,
) -> Optional[Dict[str, str]]:
    """``(name, region)`` 双键查 fields_meta；找不到 → None."""
    for f in fields_meta:
        if f[FIELD_NAME] == name and f[FIELD_REGION] == region:
            return f
    return None


def _kind_for_node(stem: str) -> str:
    """``FileInfo`` 单独标 kind（``KIND_FILEINFO``），其余统一 ``Table``."""
    if stem == ROOT_TAG:
        return KIND_FILEINFO
    return KIND_TABLE


def _wrapper_type(element: Optional[str], stem: str) -> Optional[str]:
    """wrapper 元素（如 ``# @element:ResTbl``）的 type-attr 值 = stem.

    自命名（``<self>`` / FileInfo）返回 None，前端不展 badge.
    """
    if element is None or element == ELEMENT_SELF or element == ROOT_TAG:
        return None
    if element == stem:
        return None
    return stem


# endregion

# region yaml body parsing ──────────────────────────────────────────────────
def _parse_element_header(text: str) -> Optional[str]:
    """解析首行 ``# @element:<X>``，返回 ``<X>``；缺失返回 None."""
    first = text.split("\n", 1)[0].strip()
    prefix = f"# {ANNOT_ELEMENT}"
    if first.startswith(prefix):
        return first[len(prefix):].strip()
    return None


def _extract_records(body: Any) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """yaml body → (records, table_attributes).

    body 形态分类：
    - ``None`` → ([], {})
    - ``list[Mapping]`` → 多 instance flat：records = list 元素，无 table attrs
    - ``Mapping`` 顶层 key 含 ``@related:count`` EOL 注解 → 该 key 的值是 inner
      records list（None 表示空 wrapper），其余 scalar key 进 table_attributes
    - ``Mapping`` 无 count 锚 + 含至少一个 list-of-mapping value → 该 list 是 records
    - ``Mapping`` 全 scalar 无 count 锚 → records = [body]（自命名 flat single instance）

    record 结构统一三区域 ``{index, attribute, ref}``；legacy 数据全进 ``attribute``。
    """
    if body is None:
        return [], {}
    if isinstance(body, list):
        return [_to_record(entry) for entry in body if isinstance(entry, dict)], {}
    if not isinstance(body, dict):
        return [], {}
    count_anchor = _find_count_anchor(body)
    inner_records, table_attrs = _split_body(body, count_anchor)
    if count_anchor is not None or inner_records:
        return inner_records, table_attrs
    return [_to_record(body)], {}


def _find_count_anchor(body: Any) -> Optional[str]:
    """扫顶层 key 的 EOL 注释，返回首个含 ``@related:count`` 的 key 名."""
    if not isinstance(body, CommentedMap):
        return None
    for k in body:
        cmt = trailing_comment(body, k)
        if cmt and ANNOT_RELATED_COUNT in cmt:
            return str(k)
    return None


def _split_body(
    body: Dict[str, Any],
    count_anchor: Optional[str],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """按 count_anchor 拆 body：anchor 值 → inner records，其余 → table attrs."""
    inner_records: List[Dict[str, Any]] = []
    table_attrs: Dict[str, Any] = {}
    for k, v in body.items():
        if k == count_anchor:
            if isinstance(v, list):
                inner_records.extend(_to_record(e) for e in v if isinstance(e, dict))
            continue
        if count_anchor is None and _is_record_list(v):
            inner_records.extend(_to_record(e) for e in v if isinstance(e, dict))
            continue
        table_attrs[str(k)] = _scalarize(v)
    return inner_records, table_attrs


def _is_record_list(v: Any) -> bool:
    """value 是否为 list 且至少含一个 dict 元素（legacy 内部 record list）."""
    return isinstance(v, list) and any(isinstance(e, dict) for e in v)


def _to_record(entry: Dict[str, Any]) -> Dict[str, Any]:
    """单 mapping → ``{index, attribute, ref}`` 三区域 record；legacy 全进 attribute."""
    return {
        REGION_INDEX: {},
        REGION_ATTRIBUTE: {str(k): _scalarize(v) for k, v in entry.items()},
        REGION_REF: {},
    }


def _scalarize(v: Any) -> Any:
    """ruamel 标量类型 → JSON-friendly 值.

    HexInt/HexCapsInt 转 ``0xHEX`` 字面字符串保留显示语义（嵌入式语境必须）；
    其余 int/float/str/bool/None 原样；list/dict 递归。
    """
    if isinstance(v, (HexCapsInt, HexInt)):
        return format_hex(v)
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, list):
        return [_scalarize(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _scalarize(x) for k, x in v.items()}
    return str(v)


def _extract_field_set(records: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """跨 records 取字段集**有序去重 union**（按出现序），区分 region."""
    seen: List[Dict[str, str]] = []
    seen_keys: set = set()
    for r in records:
        for region in _REGIONS:
            for name in r.get(region, {}):
                key = (region, name)
                if key not in seen_keys:
                    seen_keys.add(key)
                    seen.append({FIELD_NAME: name, FIELD_REGION: region})
    return seen


# endregion
