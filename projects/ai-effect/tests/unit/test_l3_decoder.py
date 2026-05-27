"""L3-b/c 解码器:按 op-kind 选 Layout,消费 word 流出命名字段树;REF 递归。"""

import pytest

from pa_debug.l3_analyzer.decoder import decode_op
from pa_debug.l3_analyzer.model import DecodeError, MacroHit, OpRecord
from pa_debug.l3_analyzer.schema import Atom, Dispatch, Field, I, Layout, Ref, U


def test_decode_scalar_fields_lsb_first_by_op_kind():
    op = OpRecord("pa_conv", "layer3", {"h": {"optype": "CONV"}}, [MacroHit("hac_2r", [0xABCD])])
    schema = Dispatch(
        source="h.optype",
        table={"CONV": Layout([Atom("ctrl", [Field("lo", U(8)), Field("hi", U(8))])])},
    )
    out = decode_op(op, schema, word_bits=16)
    assert out["op"] == "pa_conv"
    assert out["config"] == {"ctrl": {"lo": 0xCD, "hi": 0xAB}}  # LSB-first


def test_signed_field_sign_extends():
    op = OpRecord("x", None, {"k": "A"}, [MacroHit("m", [0xF])])  # 4 位全 1 = -1
    schema = Dispatch("k", {"A": Layout([Atom("a", [Field("s", I(4))])])})
    assert decode_op(op, schema, word_bits=4)["config"]["a"]["s"] == -1


def test_unknown_op_kind_raises():
    op = OpRecord("x", None, {"h": {"optype": "NOPE"}}, [])
    with pytest.raises(DecodeError):
        decode_op(op, Dispatch("h.optype", {}), word_bits=16)


def test_missing_op_kind_path_raises():
    op = OpRecord("x", None, {"h": {}}, [])
    with pytest.raises(DecodeError):
        decode_op(op, Dispatch("h.optype", {"CONV": Layout([])}), word_bits=16)


def test_short_word_stream_raises():
    op = OpRecord("x", None, {"k": "A"}, [MacroHit("m", [1])])
    schema = Dispatch("k", {"A": Layout([Atom("a", [Field("f", U(40))])])})
    with pytest.raises(DecodeError):
        decode_op(op, schema, word_bits=16)  # 16 位 < 40


class _FakeResolver:
    def __init__(self, table: dict[tuple[str, int], list[int]]) -> None:
        self.table = table

    def fetch(self, blob: str, addr: int) -> list[int]:
        return self.table[(blob, addr)]


def test_ref_field_follows_address_and_recursively_decodes():
    sub = Layout([Atom("w", [Field("v", U(8))])])
    op = OpRecord("x", None, {"k": "A"}, [MacroHit("m", [5, 0x7F])])
    schema = Dispatch("k", {"A": Layout([Atom("hdr", [Field("ptr", Ref(8, "weights", sub))])])})
    resolver = _FakeResolver({("weights", 5): [0x7F]})
    out = decode_op(op, schema, resolver=resolver, word_bits=8)
    assert out["config"]["hdr"]["ptr"] == {"w": {"v": 0x7F}}


def test_ref_without_resolver_raises():
    sub = Layout([Atom("w", [Field("v", U(8))])])
    op = OpRecord("x", None, {"k": "A"}, [MacroHit("m", [5])])
    schema = Dispatch("k", {"A": Layout([Atom("hdr", [Field("ptr", Ref(8, "b", sub))])])})
    with pytest.raises(DecodeError):
        decode_op(op, schema, word_bits=8)  # 没注入 resolver
