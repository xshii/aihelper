"""6 种 merge 策略实现 + ``concat(<sep>)`` 解析器。

所有策略接收一组同字段的多个值（已剔除等值情况，调用方传入的是真实差异集），
返回合并后的单一值；``conflict`` 策略检测到差异即抛 ``ConflictError``。
"""
from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple

_FUNC_CALL_RE = re.compile(r"^(\w+)\((.*)\)$", re.DOTALL)


class ConflictError(ValueError):
    """``@merge: conflict`` 字段在多个 record 间不一致时抛出."""


def parse_merge_rule(raw: str) -> Tuple[str, Optional[str]]:
    """解析 merge rule 字符串 → ``(op, arg)``.

    例：

    >>> parse_merge_rule("concat(',')")
    ('concat', ',')
    >>> parse_merge_rule("sum")
    ('sum', None)
    >>> parse_merge_rule("conflict")
    ('conflict', None)
    >>> parse_merge_rule('concat("; ")')
    ('concat', '; ')
    """
    raw = raw.strip()
    m = _FUNC_CALL_RE.match(raw)
    if not m:
        return raw, None
    op = m.group(1)
    arg = m.group(2).strip()
    if len(arg) >= 2 and arg[0] in ("'", '"') and arg[-1] == arg[0]:
        arg = arg[1:-1]
    return op, arg


def apply_merge(rule: str, values: List[Any]) -> Any:
    """按 ``rule`` 合并多个 value；未知 op 抛 ``ValueError``."""
    op, arg = parse_merge_rule(rule)
    if op == "concat":
        sep = arg if arg is not None else ","
        return sep.join(str(v) for v in values if v is not None)
    if op == "sum":
        return sum(v for v in values if v is not None)
    if op == "max":
        return max(v for v in values if v is not None)
    if op == "min":
        return min(v for v in values if v is not None)
    if op == "union":
        seen: set = set()
        out: list = []
        for v in values:
            if v is None or v in seen:
                continue
            seen.add(v)
            out.append(v)
        return out
    if op == "conflict":
        unique = {repr(v) for v in values}
        if len(unique) > 1:
            raise ConflictError(
                f"@merge: conflict 字段值不一致：{values!r}"
            )
        return values[0]
    raise ValueError(f"未知 merge op: {op!r} (rule={rule!r})")
