"""L3-b/c 引擎:按 op-kind 选 Layout,顺序消费 word 流出命名字段树;REF 经 resolver 递归。纯函数。"""

from __future__ import annotations

from .bits import BitReader
from .model import DecodeError, OpRecord
from .resolver import BlobResolver
from .schema import Atom, Dispatch, I, Ref, U


def _dig(fields: dict, path: str) -> object:
    cur: object = fields
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            raise DecodeError(f"op-kind 路径 {path!r} 在记录里找不到")
        cur = cur[key]
    return cur


def _decode_field(
    ftype: object, reader: BitReader, resolver: BlobResolver | None, word_bits: int
) -> int | dict:
    match ftype:
        case U(bits=b):
            return reader.read(b)
        case I(bits=b):
            v = reader.read(b)
            return v - (1 << b) if v >> (b - 1) else v
        case Ref(bits=b, blob=blob, schema=sub):
            if resolver is None:
                raise DecodeError("遇到 REF 字段但未注入 resolver")
            addr = reader.read(b)
            sub_reader = BitReader(resolver.fetch(blob, addr), word_bits)
            return {a.name: _decode_atom(a, sub_reader, resolver, word_bits) for a in sub.atoms}
        case _:
            raise DecodeError(f"不支持的字段类型: {ftype!r}")


def _decode_atom(
    atom: Atom, reader: BitReader, resolver: BlobResolver | None, word_bits: int
) -> dict:
    return {f.name: _decode_field(f.type, reader, resolver, word_bits) for f in atom.fields}


def decode_op(
    op: OpRecord,
    dispatch: Dispatch,
    resolver: BlobResolver | None = None,
    word_bits: int = 32,
) -> dict:
    kind = _dig(op.fields, dispatch.source)
    if kind not in dispatch.table:
        raise DecodeError(f"未知 op-kind: {kind!r}")
    layout = dispatch.table[kind]
    words = [w for m in op.macros for w in m.words]
    reader = BitReader(words, word_bits)
    config = {a.name: _decode_atom(a, reader, resolver, word_bits) for a in layout.atoms}
    return {"op": op.op, "fn": op.fn, "fields": op.fields, "config": config}
