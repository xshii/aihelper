"""BufferRegistry 单测."""
from __future__ import annotations

import zlib

import pytest

from proto_test.runtime.buffer_registry import (
    BufferKind, BufferRegistry, BufferRegistryFull,
)


def test_alloc_returns_monotonic_id():
    reg = BufferRegistry(capacity=4)
    a = reg.alloc(BufferKind.INPUT, 100)
    b = reg.alloc(BufferKind.INPUT, 100)
    c = reg.alloc(BufferKind.GOLDEN, 200)
    assert a == 1 and b == 2 and c == 3


def test_alloc_zero_size_rejected():
    reg = BufferRegistry()
    with pytest.raises(ValueError):
        reg.alloc(BufferKind.INPUT, 0)


def test_capacity_full_raises():
    reg = BufferRegistry(capacity=2)
    reg.alloc(BufferKind.INPUT, 10)
    reg.alloc(BufferKind.INPUT, 10)
    with pytest.raises(BufferRegistryFull):
        reg.alloc(BufferKind.INPUT, 10)


def test_capacity_full_caught_by_autotest_error():
    """BufferRegistryFull 应在 AutotestError 异常树里。"""
    from proto_test import AutotestError
    reg = BufferRegistry(capacity=1)
    reg.alloc(BufferKind.INPUT, 10)
    with pytest.raises(AutotestError):
        reg.alloc(BufferKind.INPUT, 10)


def test_write_size_mismatch_rejected():
    reg = BufferRegistry()
    bid = reg.alloc(BufferKind.INPUT, 10)
    with pytest.raises(ValueError):
        reg.write(bid, b"\x00" * 20)


def test_write_computes_crc32():
    reg = BufferRegistry()
    bid = reg.alloc(BufferKind.GOLDEN, 4)
    reg.write(bid, b"\x01\x02\x03\x04")
    expected = zlib.crc32(b"\x01\x02\x03\x04") & 0xFFFFFFFF
    assert reg.query(bid).crc32 == expected


def test_read_round_trip():
    reg = BufferRegistry()
    bid = reg.alloc(BufferKind.RESULT, 4)
    reg.write(bid, b"abcd")
    assert reg.read(bid) == b"abcd"


def test_read_before_write_raises():
    reg = BufferRegistry()
    bid = reg.alloc(BufferKind.INPUT, 10)
    with pytest.raises(KeyError, match="未 write"):
        reg.read(bid)


def test_free_removes_entry_and_data():
    reg = BufferRegistry()
    bid = reg.alloc(BufferKind.INPUT, 4)
    reg.write(bid, b"\x00" * 4)
    reg.free(bid)
    with pytest.raises(KeyError):
        reg.query(bid)


def test_list_by_kind():
    reg = BufferRegistry()
    reg.alloc(BufferKind.INPUT, 1)
    reg.alloc(BufferKind.INPUT, 2)
    reg.alloc(BufferKind.GOLDEN, 3)
    inputs = reg.list_by_kind(BufferKind.INPUT)
    goldens = reg.list_by_kind(BufferKind.GOLDEN)
    assert len(inputs) == 2
    assert len(goldens) == 1


def test_buf_id_not_reused_after_free():
    reg = BufferRegistry()
    a = reg.alloc(BufferKind.INPUT, 1)
    reg.free(a)
    b = reg.alloc(BufferKind.INPUT, 1)
    assert b > a                                    # 单调递增不复用
