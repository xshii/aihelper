"""L3 通用比对:按 key 对齐两份导出记录,递归比任意嵌套结构,出字段级变更。

与具体日志/字段无关——只吃 list[dict]。导出端(export)负责把日志变成可比的 dict,
本引擎对配置、结果、依赖一视同仁。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Change:
    path: str  # 字段路径,如 "deps[0].tid"
    left: object
    right: object


@dataclass
class OpDiff:
    key: tuple
    status: str  # "added" | "removed" | "changed"
    changes: list[Change]


@dataclass
class DiffReport:
    diffs: list[OpDiff] = field(default_factory=list)


def diff_value(a: object, b: object, path: str) -> list[Change]:
    """递归比较两个值,返回字段级变更。一侧为 None 时视作空 dict/list,出全量增删。"""
    if a == b:
        return []
    if isinstance(a, dict) or isinstance(b, dict):
        if (a is None or isinstance(a, dict)) and (b is None or isinstance(b, dict)):
            da = a if isinstance(a, dict) else {}
            db = b if isinstance(b, dict) else {}
            changes: list[Change] = []
            for k in list(da) + [k for k in db if k not in da]:
                child = f"{path}.{k}" if path else str(k)
                changes += diff_value(da.get(k), db.get(k), child)
            return changes
        return [Change(path, a, b)]
    if isinstance(a, list) or isinstance(b, list):
        if (a is None or isinstance(a, list)) and (b is None or isinstance(b, list)):
            sa = a if isinstance(a, list) else []
            sb = b if isinstance(b, list) else []
            out: list[Change] = []
            for i in range(max(len(sa), len(sb))):
                av = sa[i] if i < len(sa) else None
                bv = sb[i] if i < len(sb) else None
                out += diff_value(av, bv, f"{path}[{i}]")
            return out
        return [Change(path, a, b)]
    return [Change(path, a, b)]


def _key(record: dict, key_fields: tuple[str, ...]) -> tuple:
    return tuple(record[f] for f in key_fields)


def diff_records(left: list[dict], right: list[dict], key_fields: tuple[str, ...]) -> DiffReport:
    """按 key_fields 对齐两份记录,逐算子出 added/removed/changed。"""
    lmap = {_key(r, key_fields): r for r in left}
    rmap = {_key(r, key_fields): r for r in right}
    diffs: list[OpDiff] = []
    for k in list(lmap) + [k for k in rmap if k not in lmap]:
        lrec = lmap.get(k)
        rrec = rmap.get(k)
        changes = diff_value(lrec, rrec, "")
        if changes:
            status = "added" if lrec is None else "removed" if rrec is None else "changed"
            diffs.append(OpDiff(key=k, status=status, changes=changes))
    return DiffReport(diffs=diffs)
