"""基于 source offset 的源码改写。所有 Edit 按 offset 倒序应用,避免位置失效。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Edit:
    offset: int
    length: int  # 0 = 纯插入
    replacement: str


def apply_edits(source: str, edits: list[Edit]) -> str:
    for e in sorted(edits, key=lambda x: x.offset, reverse=True):
        source = source[: e.offset] + e.replacement + source[e.offset + e.length :]
    return source
