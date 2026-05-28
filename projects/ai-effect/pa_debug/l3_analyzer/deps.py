"""L3 依赖表抽取(②方案)。

hac_xr 码流按 begin/end 标记聚合成单个算子 → 按写死的公共头布局 LSB-first 切片
→ depentUint bitmap 过滤出有效依赖。

公共头布局(``OP_COMM_HEADER``)与依赖槽(``DEP_SLOTS``)写死在此,项目按真实(涉密)
结构改字段/宽度;begin/end 标记的掩码+期望值与 word 位宽走 ``DepConfig``,项目填涉密值。
解码到结构体 B/C/D 的逻辑不在这里——那是项目自己实现的 decoder 的事。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

from .bits import BitReader
from .model import DecodeError


class HeaderField(NamedTuple):
    name: str
    bits: int


class DepSlot(NamedTuple):
    label: str  # bitmap 第 i 位对应的槽名(A/B/C…)
    field: str  # 该槽在公共头里的 tid 字段名


# 写死的公共头布局,照 OpCommHeader;项目按真实结构改宽度/字段。LSB-first 顺序读。
OP_COMM_HEADER: list[HeaderField] = [
    HeaderField("tid", 16),
    HeaderField("curComputeUnit", 8),
    HeaderField("rsv", 8),
    HeaderField("depentUint", 16),
    HeaderField("dependAtid", 16),
    HeaderField("dependBtid", 16),
    HeaderField("dependCtid", 16),
]

# depentUint 的第 i 位 → 第 i 个依赖槽(置位才有效)。
DEP_SLOTS: list[DepSlot] = [
    DepSlot("A", "dependAtid"),
    DepSlot("B", "dependBtid"),
    DepSlot("C", "dependCtid"),
]


@dataclass
class DepConfig:
    """项目填的涉密值:begin/end 标记在 hac_xr 末位 word 的掩码+期望值,以及 word 位宽。"""

    begin_mask: int
    begin_value: int
    end_mask: int
    end_value: int
    word_bits: int = 32


class Dependency(NamedTuple):
    slot: str
    tid: int


@dataclass
class DependencyRecord:
    tid: int
    cur_compute_unit: int
    deps: list[Dependency]


def _hit(word: int, mask: int, value: int) -> bool:
    return word & mask == value


def aggregate_by_marker(records: list[dict], cfg: DepConfig) -> list[list[int]]:
    """扫 macro 记录:末位 word 命中 begin 开桶、命中 end 关桶,返回每个算子的扁平 word 流。"""
    ops: list[list[int]] = []
    current: list[int] | None = None
    for rec in records:
        if rec.get("kind") != "macro":
            continue
        words = list(rec["words"])
        if not words:
            raise DecodeError(f"macro {rec.get('macro')!r} 没有 word")
        last = words[-1]
        if _hit(last, cfg.begin_mask, cfg.begin_value):
            if current is not None:
                raise DecodeError("上一个算子未见 end 就遇到新 begin")
            current = []
        if current is None:
            raise DecodeError("macro 出现在 begin 之前,无法归属算子")
        current.extend(words)
        if _hit(last, cfg.end_mask, cfg.end_value):
            ops.append(current)
            current = None
    if current is not None:
        raise DecodeError("最后一个算子缺 end 标记")
    return ops


def slice_header(
    words: list[int], cfg: DepConfig, layout: list[HeaderField] | None = None
) -> dict[str, int]:
    """从算子码流头部按布局 LSB-first 顺序切出公共头字段。"""
    reader = BitReader(words, cfg.word_bits)
    return {f.name: reader.read(f.bits) for f in layout or OP_COMM_HEADER}


def _active_deps(header: dict[str, int], dep_slots: list[DepSlot]) -> list[Dependency]:
    bitmap = header["depentUint"]
    return [
        Dependency(slot=s.label, tid=header[s.field])
        for bit, s in enumerate(dep_slots)
        if bitmap & (1 << bit)
    ]


def extract_dependency_table(
    records: list[dict],
    cfg: DepConfig,
    layout: list[HeaderField] | None = None,
    dep_slots: list[DepSlot] | None = None,
) -> list[DependencyRecord]:
    """trace → 依赖表:每个算子一条(tid + 当前计算单元 + 置位的依赖)。"""
    slots = dep_slots or DEP_SLOTS
    table: list[DependencyRecord] = []
    for words in aggregate_by_marker(records, cfg):
        header = slice_header(words, cfg, layout)
        table.append(
            DependencyRecord(
                tid=header["tid"],
                cur_compute_unit=header["curComputeUnit"],
                deps=_active_deps(header, slots),
            )
        )
    return table
