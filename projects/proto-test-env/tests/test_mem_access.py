"""MemAccessAPI 单测 — ReadVal / ReadStruct / ReadArray + 边界."""
from __future__ import annotations

import struct

import pytest

from proto_test import (
    CompareEntry, Datatype, DataIntegrityError, DummyAdapter,
    SymbolNotFoundError,
)


def test_read_val_uint32(adapter: DummyAdapter):
    adapter.install_symbol("g_x", 0x100)
    adapter.write_raw(0x100, struct.pack("<I", 0xDEADBEEF))
    assert adapter.mem.ReadVal("g_x", Datatype.UINT32) == 0xDEADBEEF


def test_write_val_uint16_round_trip(adapter: DummyAdapter):
    adapter.install_symbol("g_y", 0x200)
    adapter.mem.WriteVal("g_y", Datatype.UINT16, 0x1234)
    assert adapter.read_raw(0x200, 2) == b"\x34\x12"


def test_read_struct_index_1_based(adapter: DummyAdapter):
    """index=1 = 第 1 个元素 = 数组开头。"""
    adapter.install_symbol("g_arr", 0x300)
    raw0 = struct.pack("<HHI I", 10, 0, 100, 0xAA)    # tid=10, cnt=0, length=100, addr=0xAA
    raw1 = struct.pack("<HHI I", 20, 1, 200, 0xBB)
    adapter.write_raw(0x300, raw0 + raw1)

    e1 = adapter.mem.ReadStruct("g_arr", CompareEntry, 1)
    assert e1 == {"tid": 10, "cnt": 0, "length": 100, "addr": 0xAA}

    e2 = adapter.mem.ReadStruct("g_arr", CompareEntry, 2)
    assert e2 == {"tid": 20, "cnt": 1, "length": 200, "addr": 0xBB}


def test_read_struct_index_zero_rejected(adapter: DummyAdapter):
    adapter.install_symbol("g_arr", 0x300)
    with pytest.raises(ValueError, match="1-based"):
        adapter.mem.ReadStruct("g_arr", CompareEntry, 0)


def test_read_array_uint16(adapter: DummyAdapter):
    adapter.install_symbol("g_seq", 0x400)
    adapter.write_raw(0x400, struct.pack("<HHHH", 1, 2, 3, 4))
    out = adapter.mem.ReadArray("g_seq", Datatype.UINT16, count=4)
    assert out == [1, 2, 3, 4]


def test_read_array_partial_via_start(adapter: DummyAdapter):
    adapter.install_symbol("g_seq", 0x400)
    adapter.write_raw(0x400, struct.pack("<HHHH", 1, 2, 3, 4))
    out = adapter.mem.ReadArray("g_seq", Datatype.UINT16, count=2, start=3)  # 跳前两个
    assert out == [3, 4]


def test_symbol_not_found(adapter: DummyAdapter):
    with pytest.raises(SymbolNotFoundError):
        adapter.mem.ReadVal("g_missing", Datatype.UINT32)


def test_endian_big_via_adapter():
    adapter = DummyAdapter(endian=">")
    adapter.install_symbol("g_x", 0x100)
    adapter.mem.WriteVal("g_x", Datatype.UINT32, 0x12345678)
    assert adapter.read_raw(0x100, 4) == b"\x12\x34\x56\x78"   # 大端字节序


def test_dtype_namespace():
    """``Datatype.struct.CompareEntry`` 命名空间访问。"""
    sdef = Datatype.struct.CompareEntry
    assert sdef.name == "CompareEntry"
    assert sdef.size() == 12                          # 2 + 2 + 4 + 4(PTR=32位)


def test_dtype_namespace_unregistered_raises():
    with pytest.raises(AttributeError):
        _ = Datatype.struct.NonExistent
