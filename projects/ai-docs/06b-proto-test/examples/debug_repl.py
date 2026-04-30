"""DebugConsole demo — 选项 A 架构（同进程嵌入 autotest，复用 MemAccessAPI）.

跑法::

    python examples/debug_repl.py

会话样例（用户输入加注释）::

    debug> g_compareBufDebugCnt          # 查变量（默认 UINT32）
    g_compareBufDebugCnt = 3 (0x3)

    debug> d g_compareBufCompAddr 32     # hex-dump 32 字节
    0x00001100  0a 00 00 00 64 00 00 00 ...

    debug> ! DUT_DBG_ClientHandshake     # 调被测系统函数（demo 用 Python wrapper 模拟）
    [client] read region magic at 0x10000000: 0xd06dbe60
    [client] read RTT magic
    => 0

    debug> quit
"""
from __future__ import annotations

import sys

from proto_test import (
    CompareEntry,
    Datatype,
    DebugConsole,
    DummyAdapter,
)


# region 被测系统函数 — Python wrapper 模拟桩 CPU 端 C 函数 ──────
# 真部署里这层 wrapper 内部通过 autotest 的 svc RPC 通道调桩 CPU。
# demo 直接用 MemAccessAPI 操作 DummyAdapter 的内存，不走真链路。

def make_dut_dbg_handshake(adapter: DummyAdapter):
    """对应 06a/stub_cpu/dut_dbg_client.c::DUT_DBG_ClientHandshake."""
    REGION_MAGIC_ADDR = 0x100000        # demo 用相对小地址（DummyAdapter mem_size 限制）
    DUT_DBG_REGION_MAGIC = 0xD06DBE60

    def _handshake() -> int:
        magic = int.from_bytes(adapter.read_raw(REGION_MAGIC_ADDR, 4), "little")
        print(f"[client] read region magic at 0x{REGION_MAGIC_ADDR:08x}: 0x{magic:x}")
        if magic != DUT_DBG_REGION_MAGIC:
            print(f"[client] FAIL: magic mismatch (want 0x{DUT_DBG_REGION_MAGIC:x})")
            return -1
        print("[client] handshake OK")
        return 0

    return _handshake


def make_svc_compare_pull_batch(adapter: DummyAdapter):
    """对应 06b/stub_cpu/svc_compare.c::SVC_COMPARE_PullBatch."""
    def _pull() -> int:
        n = adapter.mem.ReadVal("g_compareBufDebugCnt", Datatype.UINT32)
        print(f"[svc] g_compareBufDebugCnt = {n}")
        for i in range(1, n + 1):
            entry = adapter.mem.ReadStruct("g_compareBufCompAddr", CompareEntry, i)
            print(f"[svc]   entry[{i-1}]: tid={entry['tid']} cnt={entry['cnt']} "
                  f"length={entry['length']} addr=0x{entry['addr']:x}")
        return n

    return _pull
# endregion


def setup_dummy_dut(adapter: DummyAdapter) -> None:
    """填充模拟 DUT 内存：region magic + 比数缓冲示例数据."""
    adapter.write_raw(0x100000, (0xD06DBE60).to_bytes(4, "little"))
    adapter.install_symbol("g_compareBufDebugCnt", 0x1000)
    adapter.install_symbol("g_compareBufCompAddr", 0x1100)
    adapter.mem.WriteVal("g_compareBufDebugCnt", Datatype.UINT32, 3)
    for i, (tid, cnt, length, addr) in enumerate(
        [(0x10, 0, 100, 0x4000), (0x10, 1, 200, 0x4100), (0x20, 0, 64, 0x4200)],
        start=1,
    ):
        adapter.mem.WriteStruct(
            "g_compareBufCompAddr", CompareEntry, i,
            {"tid": tid, "cnt": cnt, "length": length, "addr": addr},
        )


def main() -> None:
    adapter = DummyAdapter(mem_size=1 << 24, endian="<")
    setup_dummy_dut(adapter)

    # 选项 A：直接复用 adapter.mem（同 autotest 的 MemAccessAPI 实例）
    console = DebugConsole(
        mem=adapter.mem,
        functions={
            "DUT_DBG_ClientHandshake": make_dut_dbg_handshake(adapter),
            "SVC_COMPARE_PullBatch":   make_svc_compare_pull_batch(adapter),
        },
    )

    print("=" * 60)
    print("DebugConsole demo — 试试这些命令：")
    print("  g_compareBufDebugCnt")
    print("  d g_compareBufCompAddr 48")
    print("  ! DUT_DBG_ClientHandshake")
    print("  ! SVC_COMPARE_PullBatch")
    print("  help / quit")
    print("=" * 60)

    if not sys.stdin.isatty():
        # 非交互 (CI / pipe)：演示 handle() 单步驱动
        for line in [
            "g_compareBufDebugCnt",
            "d g_compareBufCompAddr 48",
            "! DUT_DBG_ClientHandshake",
            "! SVC_COMPARE_PullBatch",
        ]:
            print(f"debug> {line}")
            console.handle(line)
            print()
    else:
        console.run()


if __name__ == "__main__":
    main()
