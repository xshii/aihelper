"""L3-a:读 trace + 按执行顺序 bracketing 把每个 op 的 call+整套 macro 聚成 OpRecord。"""

from __future__ import annotations

import json
from pathlib import Path

from .model import DecodeError, MacroHit, OpRecord

_META = ("kind", "op", "fn")


def aggregate(records: list[dict]) -> list[OpRecord]:
    """一条 call 开桶,后续 macro 归入当前桶,直到下一条 call(Q3 已确认顺序可靠)。"""
    ops: list[OpRecord] = []
    for rec in records:
        kind = rec.get("kind")
        if kind == "call":
            fields = {k: v for k, v in rec.items() if k not in _META}
            ops.append(OpRecord(op=rec["op"], fn=rec.get("fn"), fields=fields))
        elif kind == "macro":
            if not ops:
                raise DecodeError("macro 记录出现在任何 call 之前,无法归属")
            ops[-1].macros.append(MacroHit(name=rec["macro"], words=list(rec["words"])))
        else:
            raise DecodeError(f"未知 trace 记录 kind: {kind!r}")
    return ops


def load_trace(path: str | Path) -> list[dict]:
    lines = Path(path).read_text().splitlines()
    return [json.loads(ln) for ln in lines if ln.strip()]
