"""L3 数据模型。OpRecord 是聚合产物,喂给解码器。"""

from __future__ import annotations

from dataclasses import dataclass, field


class DecodeError(Exception):
    """trace 边界错误(坏记录 / 缺 op-kind / word 流不足 / 未知 blob)。"""


@dataclass
class MacroHit:
    name: str
    words: list[int] = field(default_factory=list)


@dataclass
class OpRecord:
    op: str
    fn: str | None
    fields: dict  # call 记录里除 kind/op/fn 外的全部(含公共头结构体、指针、标量)
    macros: list[MacroHit] = field(default_factory=list)
