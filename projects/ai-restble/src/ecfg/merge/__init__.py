"""多 team YAML 合并引擎（merge-spec 用例）。

入口：``merge_tables(tables, schema) -> Table``。规则参考 ``docs/merge-spec.md``。
"""
from ecfg.merge.merger import merge_tables  # noqa: F401
from ecfg.merge.policies import ConflictError, apply_merge, parse_merge_rule  # noqa: F401
