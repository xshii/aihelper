"""§ 1.6 机制 B 比数协议端到端单测."""
from __future__ import annotations

import struct

import pytest

from proto_test import (
    CompareBufOverflow, CompareEntry, Datatype, DummyAdapter,
    MemoryCompareDriver, run_compare_round, soft_compare,
)
from proto_test.compare import MAX_ENTRIES


# region 工具：模拟 DUT 固件填充 ──────────────────────────────────
def _fw_publish_entries(
    adapter: DummyAdapter, entries: list, data_base: int = 0x4000
) -> None:
    """模拟固件：先写 g_compAddr 描述符 + 数据，最后递增 g_debugCnt（顺序至关重要）。"""
    addr = data_base
    descriptor_addrs = []
    data_blocks = []
    for tid, cnt, payload in entries:
        descriptor_addrs.append(
            (tid, cnt, len(payload), addr)
        )
        data_blocks.append((addr, payload))
        addr += len(payload)

    # 先写数据
    for waddr, payload in data_blocks:
        adapter.write_raw(waddr, payload)
    # 再写描述符
    for i, (tid, cnt, length, daddr) in enumerate(descriptor_addrs, start=1):
        adapter.mem.WriteStruct(
            "g_compAddr", CompareEntry, i,
            {"tid": tid, "cnt": cnt, "length": length, "addr": daddr},
        )
    # 最后才更新 cnt（生产 / 消费协议关键）
    adapter.mem.WriteVal("g_debugCnt", Datatype.UINT32, len(entries))
# endregion


def test_pull_empty_batch(cmp_driver: MemoryCompareDriver):
    """g_debugCnt == 0 → 空批，不抛错。"""
    assert cmp_driver.pull_compare_batch() == []


def test_pull_single_entry(
    adapter_with_compare_symbols: DummyAdapter, cmp_driver: MemoryCompareDriver
):
    _fw_publish_entries(
        adapter_with_compare_symbols,
        [(0x0001, 0, b"\xAA\xBB\xCC\xDD")],
    )
    batch = cmp_driver.pull_compare_batch()
    assert len(batch) == 1
    entry, data = batch[0]
    assert entry["tid"] == 0x0001
    assert entry["cnt"] == 0
    assert entry["length"] == 4
    assert data == b"\xAA\xBB\xCC\xDD"


def test_pull_multiple_entries_order(
    adapter_with_compare_symbols: DummyAdapter, cmp_driver: MemoryCompareDriver
):
    """3 项；顺序保留。"""
    _fw_publish_entries(
        adapter_with_compare_symbols,
        [
            (0x10, 0, b"\x01" * 16),
            (0x10, 1, b"\x02" * 16),                  # 同 tid 不同 cnt
            (0x20, 0, b"\x03" * 16),
        ],
    )
    batch = cmp_driver.pull_compare_batch()
    assert [e["tid"] for e, _ in batch] == [0x10, 0x10, 0x20]
    assert [e["cnt"] for e, _ in batch] == [0, 1, 0]


def test_overflow_raises(
    adapter_with_compare_symbols: DummyAdapter, cmp_driver: MemoryCompareDriver
):
    """g_debugCnt 越界 → CompareBufOverflow。"""
    adapter_with_compare_symbols.mem.WriteVal(
        "g_debugCnt", Datatype.UINT32, MAX_ENTRIES + 1
    )
    with pytest.raises(CompareBufOverflow):
        cmp_driver.pull_compare_batch()


def test_overflow_caught_by_autotest_error(
    adapter_with_compare_symbols: DummyAdapter, cmp_driver: MemoryCompareDriver
):
    """CompareBufOverflow 应在 AutotestError 异常树里。"""
    from proto_test import AutotestError
    adapter_with_compare_symbols.mem.WriteVal(
        "g_debugCnt", Datatype.UINT32, MAX_ENTRIES + 5
    )
    with pytest.raises(AutotestError):
        cmp_driver.pull_compare_batch()


def test_clear_compare_buf(
    adapter_with_compare_symbols: DummyAdapter, cmp_driver: MemoryCompareDriver
):
    adapter_with_compare_symbols.mem.WriteVal("g_debugCnt", Datatype.UINT32, 5)
    cmp_driver.clear_compare_buf()
    assert adapter_with_compare_symbols.mem.ReadVal(
        "g_debugCnt", Datatype.UINT32
    ) == 0


def test_run_compare_round_pass(
    adapter_with_compare_symbols: DummyAdapter, cmp_driver: MemoryCompareDriver
):
    """端到端：发布 → 拉 → 软比 → 清零；GOLDEN 全匹配 → PASS。"""
    payload = b"\xAA" * 32
    _fw_publish_entries(adapter_with_compare_symbols, [(0x10, 0, payload)])
    golden = {(0x10, 0): payload}
    results = run_compare_round(cmp_driver, golden)
    assert len(results) == 1
    assert results[0].passed
    assert results[0].diff_bytes == 0
    # 已清零
    assert adapter_with_compare_symbols.mem.ReadVal(
        "g_debugCnt", Datatype.UINT32
    ) == 0


def test_run_compare_round_fail(
    adapter_with_compare_symbols: DummyAdapter, cmp_driver: MemoryCompareDriver
):
    payload_actual = b"\xAA" * 32
    payload_golden = b"\xBB" * 32                      # 全异
    _fw_publish_entries(adapter_with_compare_symbols, [(0x10, 0, payload_actual)])
    golden = {(0x10, 0): payload_golden}
    results = run_compare_round(cmp_driver, golden)
    assert results[0].diff_bytes == 32
    assert not results[0].passed


def test_soft_compare_size_mismatch():
    """实际长度与 GOLDEN 不一致 → diff = max(len)（保守判 FAIL）。"""
    entry = {"tid": 0, "cnt": 0, "length": 8, "addr": 0}
    r = soft_compare(entry, b"\x00" * 8, b"\x00" * 4)
    assert r.diff_bytes == 8
