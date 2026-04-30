"""典型用例 demo — Autotest 端到端编排（机制 A 发包 + 机制 B 比数）.

本例不连真硬件，跑在 ``DummyAdapter`` + ``MockL6APort`` 上：
1. 机制 A：业务自由拼 → DDR 切片 → 走 ``FpgaAdapter`` (load → start → wait → compare)
2. 机制 B：模拟 DUT 固件填充 ``g_compareBufDebugCnt`` + ``g_compareBufCompAddr`` → 拉批 → 软比

Usage::

    python examples/case_typical.py
"""
from __future__ import annotations

import struct

from proto_test import (
    Baseline,
    Case,
    CompareEntry,
    Datatype,
    DdrConfig,
    DdrSender,
    DummyAdapter,
    FpgaAdapter,
    MemoryCompareDriver,
    MemoryMechanism,
    MessageMechanism,
    MockL6APort,
    Via,
    pack,
    run_compare_round,
)


def build_fpga_adapter(adapter: DummyAdapter) -> tuple[FpgaAdapter, MockL6APort]:
    """装配 FpgaAdapter：MockL6APort + MessageMechanism + MemoryMechanism."""
    l6a = MockL6APort()
    mech_msg = MessageMechanism(l6a=l6a, timer_period_us=200)
    mech_mem = MemoryMechanism(mem=adapter.mem, cfg_region_base=0x2000)
    return FpgaAdapter(mech_msg=mech_msg, mech_mem=mech_mem, default_via=Via.VIA_MSG), l6a


def demo_mechanism_a(fpga: FpgaAdapter, l6a: MockL6APort) -> None:
    """机制 A 完整流程：业务自由拼 + DDR 分片 + 走 FpgaAdapter 端到端.

    分层（外 → 内）::
        DATA_BUF
        └── DdrChunk × N         ← DdrSender.send() 自动切片 + 填块头 + 自增 block_id
            ├── DdrBlockHeader (512B 含分片标志)
            └── payload          ← 业务层用 struct.pack 自由拼
    """
    sender = DdrSender(DdrConfig(channel_id=0x100, priority=1))

    vport_hdr = struct.pack("<HHI", 0x100, 0x0, 0)
    biz_hdr = struct.pack("<II", 0xCAFE0001, 0x12345678)
    biz_field = b"\xAB" * 5000                                 # 故意触发分片
    full_payload = vport_hdr + biz_hdr + biz_field             # 5016B

    chunks = sender.send(full_payload)
    raw = pack(chunks)
    print(f"[A] 业务 payload {len(full_payload)}B → {len(chunks)} 个 DDR chunk → DATA_BUF {len(raw)}B")
    for i, ch in enumerate(chunks):
        h = ch.header
        print(f"[A]   chunk #{i}: frag_flag={h.frag_flag} "
              f"seq={h.frag_seq}/{h.frag_total} "
              f"payload_length={h.payload_length}B "
              f"block_id={h.block_id}")

    # 端到端：load → start → wait → standard_compare
    baseline = Baseline(image="demo.img", do_path="demo.do", golden_dir="g", gc_version="v1")
    case = Case(case_id="demo_a", baseline=baseline)
    fpga.load_version({})
    fpga.start_business(case, payload=raw)
    result = fpga.wait_result(case, timeout_s=1.0)
    cmp_result = fpga.run_standard_compare(case, golden={})

    print(f"[A] L6A 收到 {len(l6a.sent_buffers)} 笔，共 {l6a.total_bytes_sent}B；"
          f"timer_period={l6a.timer_period_us}us; started={l6a.started}")
    print(f"[A] FSM={fpga.fsm.state.value}; "
          f"raw_status={result.raw_status}; "
          f"verdict={cmp_result.to_verdict().value}")


def demo_mechanism_b(adapter: DummyAdapter) -> None:
    """机制 B：模拟 DUT 填 g_compareBufDebugCnt + g_compareBufCompAddr → 比数。"""
    adapter.install_symbol("g_compareBufDebugCnt", 0x1000)
    adapter.install_symbol("g_compareBufCompAddr", 0x1100)

    payloads = [
        (0x10, 0, b"\xAA" * 8),
        (0x10, 1, b"\xBB" * 16),                      # 同 tid 不同 cnt
        (0x20, 0, b"\xCC" * 32),
    ]
    data_addr = 0x4000
    for i, (tid, cnt, payload) in enumerate(payloads, start=1):
        adapter.write_raw(data_addr, payload)
        adapter.mem.WriteStruct(
            "g_compareBufCompAddr", CompareEntry, i,
            {"tid": tid, "cnt": cnt, "length": len(payload), "addr": data_addr},
        )
        data_addr += len(payload)
    adapter.mem.WriteVal("g_compareBufDebugCnt", Datatype.UINT32, len(payloads))

    # GOLDEN：第 2 项故意改一个字节 → 应 FAIL
    golden = {
        (0x10, 0): b"\xAA" * 8,
        (0x10, 1): b"\xBB" * 15 + b"\xFF",
        (0x20, 0): b"\xCC" * 32,
    }

    drv = MemoryCompareDriver(mem=adapter.mem)
    results = run_compare_round(drv, golden)
    for r in results:
        verdict = "PASS" if r.passed else f"FAIL ({r.diff_bytes}B 差异)"
        print(f"[B] tid=0x{r.tid:04X} cnt={r.cnt} length={r.length} → {verdict}")


def main() -> None:
    adapter = DummyAdapter(mem_size=1 << 20, endian="<")
    fpga, l6a = build_fpga_adapter(adapter)

    print("=== 机制 A：DDR 块头 + 分片 + FpgaAdapter 端到端 ===")
    demo_mechanism_a(fpga, l6a)
    print()
    print("=== 机制 B：内存契约比数 ===")
    demo_mechanism_b(adapter)


if __name__ == "__main__":
    main()
