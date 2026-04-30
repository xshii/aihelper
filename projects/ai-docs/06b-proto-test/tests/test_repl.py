"""DebugConsole smoke — 三个原子能力（查变量 / 查内存 / 调函数）."""
from __future__ import annotations

import io

import pytest

from proto_test import CompareEntry, Datatype, DebugConsole, DummyAdapter


@pytest.fixture
def adapter() -> DummyAdapter:
    a = DummyAdapter(mem_size=1 << 16, endian="<")
    a.install_symbol("g_x", 0x1000)
    a.install_symbol("g_arr", 0x1100)
    a.mem.WriteVal("g_x", Datatype.UINT32, 0x2A)
    a.mem.WriteStruct(
        "g_arr", CompareEntry, 1,
        {"tid": 10, "cnt": 0, "length": 100, "addr": 0xABCD},
    )
    return a


@pytest.fixture
def console(adapter: DummyAdapter) -> tuple[DebugConsole, io.StringIO]:
    out = io.StringIO()
    c = DebugConsole(
        mem=adapter.mem,
        functions={"echo_one": lambda: (print("[hello]"), 1)[1]},
        output=out,
    )
    return c, out


def test_read_symbol_default_dtype(console):
    c, out = console
    c.handle("g_x")
    assert "g_x = 42 (0x2a)" in out.getvalue()


def test_read_symbol_explicit_dtype(console):
    c, out = console
    c.handle("g_x:UINT16")
    assert "g_x = 42 (0x2a)" in out.getvalue()


def test_read_symbol_unknown_dtype(console):
    """handle() 抛出原始异常；run() 才 catch 并打 ERROR 行。"""
    c, _ = console
    with pytest.raises(ValueError, match="unknown dtype"):
        c.handle("g_x:NOTREAL")


def test_dump_by_address(console):
    c, out = console
    c.handle("d 0x1000 4")
    text = out.getvalue()
    assert "0x00001000" in text
    assert "2a 00 00 00" in text


def test_dump_by_symbol(console):
    c, out = console
    c.handle("d g_arr 16")
    text = out.getvalue()
    assert "0x00001100" in text
    # CompareEntry: tid=10 (LE) → "0a 00", cnt=0 → "00 00", length=100 → "64 00 00 00"
    assert "0a 00 00 00 64 00 00 00" in text


def test_dump_default_length(console):
    c, out = console
    c.handle("d 0x1000")
    # 默认 16 字节 → 一行输出
    assert out.getvalue().count("0x00001000") == 1


def test_dump_usage_on_empty(console):
    c, out = console
    c.handle("d")
    assert "usage:" in out.getvalue()


def test_call_function_with_echo(console):
    c, out = console
    c.handle("! echo_one")
    text = out.getvalue()
    assert "[hello]" in text          # DEBUG 回显（被调函数 stdout）
    assert "=> 1" in text               # 返回值


def test_call_unknown_function(console):
    c, out = console
    c.handle("! does_not_exist")
    assert "ERROR" in out.getvalue() and "unknown function" in out.getvalue()


def test_call_with_int_args(adapter: DummyAdapter):
    captured: list = []
    out = io.StringIO()

    def my_fn(a, b):
        captured.append((a, b))
        return a + b

    c = DebugConsole(mem=adapter.mem, functions={"my_fn": my_fn}, output=out)
    c.handle("! my_fn 10 0x20")
    assert captured == [(10, 0x20)]
    assert "=> 42" in out.getvalue()    # 10 + 32 = 42


def test_call_usage_on_empty(console):
    c, out = console
    c.handle("!")
    assert "usage:" in out.getvalue()


def test_dispatch_unknown_symbol_raises_caught(console):
    """非法符号在 run() 里被 catch；handle() 直接抛出。"""
    c, out = console
    with pytest.raises(Exception):
        c.handle("g_does_not_exist")
