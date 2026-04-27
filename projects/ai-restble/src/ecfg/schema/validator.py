"""Schema 驱动的数据校验。

两个时机：
- ``validate_schema(schema)`` — schema 加载期：检查 schema 自身不变量
- ``validate_table(table, schema)`` — 运行期：对单张 table 的 records 应用约束
  （index 唯一性 + range/enum per-record）

参考 docs/merge-spec.md §7.2 / §7.1。
"""
from __future__ import annotations

from typing import Any

from ecfg.model import Table
from ecfg.schema.model import FieldSchema, TableSchema


class ValidationError(ValueError):
    """schema 不变量或 record 数据校验失败时抛出."""


def validate_schema(schema: TableSchema) -> None:
    """schema 加载期校验：index 字段不应同时在 attribute / ref 区."""
    attr_overlap = set(schema.index_fields) & set(schema.attribute_fields)
    if attr_overlap:
        raise ValidationError(
            f"{schema.base_name}: index 字段同时在 attribute 区: {sorted(attr_overlap)}"
        )
    ref_overlap = set(schema.index_fields) & set(schema.ref_fields)
    if ref_overlap:
        raise ValidationError(
            f"{schema.base_name}: index 字段同时在 ref 区: {sorted(ref_overlap)}"
        )


def validate_table(table: Table, schema: TableSchema) -> None:
    """运行期校验：单张 table 的每条 record 满足 schema 约束."""
    _check_index_uniqueness(table, schema)
    _check_field_constraints(table, schema)


def _check_index_uniqueness(table: Table, schema: TableSchema) -> None:
    if not schema.index_fields:
        return
    seen: set = set()
    for i, rec in enumerate(table.records):
        idx = tuple(_to_hashable(rec.index.get(f)) for f in schema.index_fields)
        if idx in seen:
            raise ValidationError(
                f"{table.base_name}[{i}]: 重复 index {idx}（违反唯一性）"
            )
        seen.add(idx)


def _check_field_constraints(table: Table, schema: TableSchema) -> None:
    for i, rec in enumerate(table.records):
        for name, fs in schema.attribute_fields.items():
            value = rec.attribute.get(name)
            if value is None:
                continue  # 缺失视为 null，不查 range/enum
            _check_range(table.base_name, i, name, value, fs)
            _check_enum(table.base_name, i, name, value, fs)


def _check_range(base: str, idx: int, name: str, value: Any, fs: FieldSchema) -> None:
    if fs.range_lo is None or fs.range_hi is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(
            f"{base}[{idx}].{name}: @range 字段值非数值: {value!r}"
        )
    if not fs.range_lo <= value <= fs.range_hi:
        raise ValidationError(
            f"{base}[{idx}].{name}: 值 {value} 越界 [{fs.range_lo}, {fs.range_hi}]"
        )


def _check_enum(base: str, idx: int, name: str, value: Any, fs: FieldSchema) -> None:
    if not fs.enum_values:
        return
    if str(value) not in fs.enum_values:
        raise ValidationError(
            f"{base}[{idx}].{name}: 值 {value!r} 不在 enum 集 {fs.enum_values}"
        )


def _to_hashable(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(value)
    return value
