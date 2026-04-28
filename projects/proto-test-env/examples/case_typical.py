"""典型用例 demo — Autotest 端到端编排（机制 A 发包 + 机制 B 比数）.

本例不连真硬件，跑在 ``DummyAdapter`` 上：
1. 机制 A：组合 ``HeaderBlock + TensorBlock × 2 + EndBlock`` → 写 ``DATA_BUF``
2. 机制 B：模拟 DUT 固件填充 ``g_debugCnt`` + ``g_compAddr`` → 拉批 → 软比

Usage::

    python -m proto_test.examples.case_typical
    # 或：python examples/case_typical.py
"""
from __future__ import annotations

import struct

from proto_test import (
    CompareEntry,
    Datatype,
    DdrConfig,
    DdrSender,
    DummyAdapter,
    EndBlock,
    HeaderBlock,
    MemoryCompareDriver,
    TensorBlock,
    pack,
    run_compare_round,
)


def demo_mechanism_a(adapter: DummyAdapter) -> bytes:
    """机制 A 完整流程：业务自由拼 + DDR 分片填写 + 写 DATA_BUF.

    分层（外 → 内）::
        DATA_BUF
        └── DdrChunk × N         ← DdrSender.send() 自动切片 + 填块头 + 自增 block_id
            ├── DdrBlockHeader (512B 含分片标志)
            └── payload          ← 业务层用 struct.pack 自由拼
                ├── VPORT 头
                ├── 业务 header
                └── 业务字段
    """
    # DDR 层：构造一次 sender，复用整个 case
    sender = DdrSender(DdrConfig(channel_id=0x100, priority=1))

    # 业务层：用户用 struct.pack 任意拼（此处仅占位）
    vport_hdr = struct.pack("<HHI", 0x100, 0x0, 0)            # 8B   VPORT id / flags / seq
    biz_hdr = struct.pack("<II", 0xCAFE0001, 0x12345678)      # 8B   业务 op / session
    biz_field = b"\xAB" * 5000                                 # 5000B 张量数据（故意触发分片）
    full_payload = vport_hdr + biz_hdr + biz_field             # 5016B

    # 一行发送：自动 block_id + 自动分片 + 自动填头
    chunks = sender.send(full_payload)
    raw = pack(chunks)                                          # 替代 bytes(sum(chunks, 0))

    print(f"[A] 业务 payload {len(full_payload)}B → 切成 {len(chunks)} 个 DDR chunk → DATA_BUF {len(raw)}B")
    for i, ch in enumerate(chunks):
        h = ch.header
        print(f"[A]   chunk #{i}: frag_flag={h.frag_flag} "
              f"seq={h.frag_seq}/{h.frag_total} "
              f"channel=0x{h.channel_id:03x} "
              f"payload_length={h.payload_length}B "
              f"block_id={h.block_id}")

    # 同一 sender 再发一笔（block_id 自增到 2）
    chunks2 = sender.send(b"\x55" * 100)
    print(f"[A] 第 2 笔（自动 block_id={chunks2[0].header.block_id}）：{len(chunks2)} chunks")
    return raw


def demo_business_block_compose() -> None:
    """旁支：业务层也可用 Block 系统拼（HeaderBlock + TensorBlock + EndBlock）。

    适用场景：业务有多种"块类型"且需要类型化组合时（替代 ad-hoc struct.pack）。
    """
    h = HeaderBlock(version=1, flags=0, count=2)
    t1 = TensorBlock(tid=0, cnt=0, data=b"\x11" * 16)
    t2 = TensorBlock(tid=1, cnt=0, data=b"\x22" * 32)
    end = EndBlock()
    buf = h + t1 + t2 + end
    print(f"[A'] 业务 Block 拼接：4 块 → {len(buf)}B (= 4 × 512)")


def demo_mechanism_b(adapter: DummyAdapter) -> None:
    """机制 B：模拟 DUT 填 g_debugCnt + g_compAddr → 比数。"""
    adapter.install_symbol("g_debugCnt", 0x1000)
    adapter.install_symbol("g_compAddr", 0x1100)

    # 模拟 DUT 固件填充
    payloads = [
        (0x10, 0, b"\xAA" * 8),
        (0x10, 1, b"\xBB" * 16),                      # 同 tid 不同 cnt
        (0x20, 0, b"\xCC" * 32),
    ]
    data_addr = 0x4000
    for i, (tid, cnt, payload) in enumerate(payloads, start=1):
        adapter.write_raw(data_addr, payload)
        adapter.mem.WriteStruct(
            "g_compAddr", CompareEntry, i,
            {"tid": tid, "cnt": cnt, "length": len(payload), "addr": data_addr},
        )
        data_addr += len(payload)
    adapter.mem.WriteVal("g_debugCnt", Datatype.UINT32, len(payloads))

    # GOLDEN：第 2 项故意改一个字节 → 应 FAIL
    golden = {
        (0x10, 0): b"\xAA" * 8,
        (0x10, 1): b"\xBB" * 15 + b"\xFF",            # 末字节不同
        (0x20, 0): b"\xCC" * 32,
    }

    drv = MemoryCompareDriver(mem=adapter.mem)
    results = run_compare_round(drv, golden)
    for r in results:
        verdict = "PASS" if r.passed else f"FAIL ({r.diff_bytes}B 差异)"
        print(f"[B] tid=0x{r.tid:04X} cnt={r.cnt} length={r.length} → {verdict}")


def main() -> None:
    adapter = DummyAdapter(mem_size=1 << 20, endian="<")
    print("=== 机制 A：DDR 块头 + 分片 + 业务自由拼 ===")
    demo_mechanism_a(adapter)
    print()
    demo_business_block_compose()
    print()
    print("=== 机制 B：内存契约比数 ===")
    demo_mechanism_b(adapter)


if __name__ == "__main__":
    main()
