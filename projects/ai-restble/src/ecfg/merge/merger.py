"""多 ``Table`` 融合引擎：按 schema 的 index 字段分组，组内按 per-field rule 合并."""
from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Dict, Iterable, List, Tuple

from ecfg.merge.policies import ConflictError, apply_merge
from ecfg.model import CellValue, Record, Table
from ecfg.schema.model import TableSchema, to_hashable
from ecfg.schema.validator import validate_schema, validate_table

logger = logging.getLogger(__name__)


def merge_tables(
    tables: List[Table], schema: TableSchema, *, validate: bool = True,
) -> Table:
    """合并多张同 ``base_name`` 的 Table → 一张 ``Table``.

    流程：
    0. ``validate=True``（默认）→ 先 ``validate_schema(schema)``
       和每张 table ``validate_table(table, schema)``，违反约束立即报错
    1. 按 schema.index_fields 拼出 identity tuple，分组 records
    2. 单 record 组直接保留
    3. 多 record 组按 per-field 规则合（attribute 看 schema.attribute_fields；
       ref 整 entry 默认 conflict 策略）

    ``validate=False`` 旁路所有校验（仅用于已知干净的 in-memory 测试数据）。
    """
    total_records = sum(len(t.records) for t in tables)
    logger.info(
        "merge_tables: %s, %d tables, %d records total, validate=%s",
        schema.base_name, len(tables), total_records, validate,
    )
    if validate:
        validate_schema(schema)
        for t in tables:
            validate_table(t, schema)
    if not tables:
        return Table(base_name=schema.base_name, records=[])

    groups: "OrderedDict[Tuple, List[Record]]" = OrderedDict()
    for t in tables:
        for r in t.records:
            key = _index_key(r, schema.index_fields)
            groups.setdefault(key, []).append(r)

    merged_records: List[Record] = []
    multi_group_count = 0
    for records in groups.values():
        if len(records) == 1:
            merged_records.append(records[0])
        else:
            merged_records.append(_merge_record_group(records, schema))
            multi_group_count += 1
    logger.info(
        "merge_tables: %s → %d records (%d groups merged from multi-source)",
        schema.base_name, len(merged_records), multi_group_count,
    )
    return Table(base_name=schema.base_name, records=merged_records)


def _index_key(rec: Record, index_fields: Iterable[str]) -> Tuple:
    """从 record 的 index 区抽 identity tuple（忽略缺失字段）."""
    return tuple((f, to_hashable(rec.index.get(f))) for f in index_fields)


def _merge_record_group(records: List[Record], schema: TableSchema) -> Record:
    """合并一组同 index 的 records；attribute 按 rule，ref 默认 conflict.

    上下文 context 通过 ``_merge_region`` 透传到错误信息：
    ``<base>[idx_field=val,...].attribute.<field>: <原始 ConflictError>``。
    """
    merged = Record(index=dict(records[0].index))
    idx_repr = ", ".join(f"{k}={v!r}" for k, v in records[0].index.items())
    context = f"{schema.base_name}[{idx_repr}]"
    merged.attribute = _merge_region(
        [r.attribute for r in records],
        {n: f.merge_rule for n, f in schema.attribute_fields.items()},
        default_rule=None,  # 无规则的 attribute 字段 → 取首条 non-None
        context=f"{context}.attribute",
    )
    merged.ref = _merge_region(
        [r.ref for r in records],
        {n: (f.merge_rule or "conflict") for n, f in schema.ref_fields.items()},
        default_rule="conflict",  # ref 默认 conflict（必须等值）
        context=f"{context}.ref",
    )
    return merged


def _merge_region(
    region_dicts: List[Dict[str, CellValue]],
    rules: Dict[str, "str | None"],
    *,
    default_rule: "str | None",
    context: str,
) -> Dict[str, CellValue]:
    """合并多个 region dict 同一字段集合；ConflictError 被重抛附加 ``context.<key>``."""
    all_keys: List[str] = []
    seen = set()
    for d in region_dicts:
        for k in d:
            if k not in seen:
                seen.add(k)
                all_keys.append(k)

    merged: Dict[str, CellValue] = {}
    for key in all_keys:
        values = [d.get(key) for d in region_dicts]
        rule = rules.get(key, default_rule) or default_rule
        if all(v == values[0] for v in values):
            merged[key] = values[0]
            continue
        if rule is None:
            # 无规则：取首条 non-None
            for v in values:
                if v is not None:
                    merged[key] = v
                    break
            else:
                merged[key] = None
        else:
            try:
                merged[key] = apply_merge(rule, values)
            except ConflictError as exc:
                raise ConflictError(f"{context}.{key}: {exc}") from exc
    return merged
