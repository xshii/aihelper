"""Schema 子系统：注解解析、TableSchema 构建、数据校验（Phase 1）。

公开 API（``from ecfg.schema import ...``）：

- ``load_table_schema(yaml_path)`` — 从 yaml 文件首部 ``TEMPLATE`` 块构建 schema
- ``TableSchema`` / ``FieldSchema`` — schema 数据类
- ``validate_schema(schema)`` / ``validate_table(table, schema)`` — 校验入口
- ``ValidationError`` — 校验失败异常
"""
from ecfg.schema.loader import load_table_schema  # noqa: F401
from ecfg.schema.model import FieldSchema, Region, TableSchema  # noqa: F401
from ecfg.schema.validator import (  # noqa: F401
    ValidationError,
    validate_schema,
    validate_table,
)
