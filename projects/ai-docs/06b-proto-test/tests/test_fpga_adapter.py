"""FpgaAdapter 集成测试 — Strategy 分发 + FSM 联动."""
from __future__ import annotations

import pytest

from proto_test import (
    Baseline, Case, DummyAdapter, FpgaAdapter,
    MemoryMechanism, MessageMechanism, MockL6APort, ModelState,
    ResultOut, Verdict, Via,
)


@pytest.fixture
def baseline() -> Baseline:
    return Baseline(image="img", do_path="do", golden_dir="g", gc_version="v1")


@pytest.fixture
def stub_l6a() -> MockL6APort:
    return MockL6APort()


@pytest.fixture
def fpga_adapter(stub_l6a: MockL6APort) -> FpgaAdapter:
    msg = MessageMechanism(l6a=stub_l6a, timer_period_us=200)
    mem_adapter = DummyAdapter(mem_size=1 << 16)
    mem_adapter.install_symbol("g_compareBufDebugCnt", 0x1000)
    mem_adapter.install_symbol("g_compareBufCompAddr", 0x1100)
    mem = MemoryMechanism(mem=mem_adapter.mem, cfg_region_base=0x2000)
    return FpgaAdapter(mech_msg=msg, mech_mem=mem, default_via=Via.VIA_MSG)


def test_dispatch_default_msg(
    fpga_adapter: FpgaAdapter, stub_l6a: MockL6APort, baseline: Baseline
):
    case = Case(case_id="c1", baseline=baseline)
    fpga_adapter.load_version({})
    fpga_adapter.start_business(case, payload=b"\x01\x02")
    assert stub_l6a.started
    assert stub_l6a.sent_buffers == [b"\x01\x02"]
    assert stub_l6a.timer_period_us == 200


def test_dispatch_via_mem_explicit(
    fpga_adapter: FpgaAdapter, stub_l6a: MockL6APort, baseline: Baseline
):
    case = Case(case_id="c2", baseline=baseline, via=Via.VIA_MEM)
    fpga_adapter.load_version({})
    fpga_adapter.start_business(case, payload=b"\xff")
    # 没碰 L6A
    assert stub_l6a.sent_buffers == []
    assert not stub_l6a.started


def test_run_standard_compare_falls_back_for_mem(
    fpga_adapter: FpgaAdapter, baseline: Baseline
):
    """case.via=VIA_MEM 时 run_standard_compare 自动走 fallback。"""
    case = Case(case_id="c3", baseline=baseline, via=Via.VIA_MEM)
    # mem 比数：g_compareBufDebugCnt=0 → 空批 → 0 diff
    result = fpga_adapter.run_standard_compare(case, golden={})
    assert result.cmp_diff_count == 0


def test_fsm_advances_through_load_and_run(
    fpga_adapter: FpgaAdapter, baseline: Baseline
):
    case = Case(case_id="c4", baseline=baseline)
    assert fpga_adapter.fsm.state == ModelState.IDLE
    fpga_adapter.load_version({})
    assert fpga_adapter.fsm.state == ModelState.READY
    fpga_adapter.start_business(case, payload=b"")
    assert fpga_adapter.fsm.state == ModelState.RUNNING
    result = fpga_adapter.wait_result(case, timeout_s=0.01)
    assert fpga_adapter.fsm.state == ModelState.DONE
    assert result.raw_status == 0


def test_verdict_pass_when_no_diff():
    """`ResultOut.to_verdict()` 直接用，不再经 adapter 包装。"""
    assert ResultOut().to_verdict() == Verdict.PASS


def test_verdict_fail_with_diff():
    assert ResultOut(cmp_diff_count=3).to_verdict() == Verdict.FAIL
