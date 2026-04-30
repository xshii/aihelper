"""FpgaAdapter 集成测试 — Strategy 分发 + FSM 联动."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import pytest

from proto_test import (
    Baseline, Case, CompareEntry, DummyAdapter, Datatype, FpgaAdapter,
    LifecycleFSM, MemoryMechanism, MessageMechanism, ModelState,
    ResultOut, Verdict, Via,
)


# region L6A stub for MessageMechanism ─────────────────────────────
@dataclass
class _StubL6A:
    sent_data: bytes = b""
    timer_period: int = 0
    started: bool = False
    poll_succeeds: bool = True
    diff_count: int = 0
    calls: List[str] = field(default_factory=list)

    def data_buf_write(self, raw: bytes) -> None:
        self.calls.append("data_buf_write")
        self.sent_data = raw

    def cfg_timer(self, period_us: int) -> None:
        self.calls.append("cfg_timer")
        self.timer_period = period_us

    def msg_send_start(self) -> None:
        self.calls.append("msg_send_start")
        self.started = True

    def msg_poll_done(self, timeout_s: float) -> bool:
        self.calls.append("msg_poll_done")
        return self.poll_succeeds

    def cmp_engine_pull(self) -> ResultOut:
        self.calls.append("cmp_engine_pull")
        return ResultOut(cmp_diff_count=self.diff_count)
# endregion


@pytest.fixture
def baseline() -> Baseline:
    return Baseline(image="img", do_path="do", golden_dir="g", gc_version="v1")


@pytest.fixture
def stub_l6a() -> _StubL6A:
    return _StubL6A()


@pytest.fixture
def fpga_adapter(stub_l6a: _StubL6A) -> FpgaAdapter:
    msg = MessageMechanism(l6a=stub_l6a, timer_period_us=200)
    mem_adapter = DummyAdapter(mem_size=1 << 16)
    mem_adapter.install_symbol("g_debugCnt", 0x1000)
    mem_adapter.install_symbol("g_compAddr", 0x1100)
    mem = MemoryMechanism(mem=mem_adapter.mem, cfg_region_base=0x2000)
    return FpgaAdapter(mech_msg=msg, mech_mem=mem, default_via=Via.VIA_MSG)


def test_dispatch_default_msg(
    fpga_adapter: FpgaAdapter, stub_l6a: _StubL6A, baseline: Baseline
):
    case = Case(case_id="c1", baseline=baseline)
    fpga_adapter.load_version({})
    fpga_adapter.start_business(case, payload=b"\x01\x02")
    assert stub_l6a.started
    assert stub_l6a.sent_data == b"\x01\x02"
    assert stub_l6a.timer_period == 200


def test_dispatch_via_mem_explicit(
    fpga_adapter: FpgaAdapter, stub_l6a: _StubL6A, baseline: Baseline
):
    case = Case(case_id="c2", baseline=baseline, via=Via.VIA_MEM)
    fpga_adapter.load_version({})
    fpga_adapter.start_business(case, payload=b"\xff")
    # 没碰 L6A
    assert stub_l6a.sent_data == b""
    assert not stub_l6a.started


def test_run_standard_compare_falls_back_for_mem(
    fpga_adapter: FpgaAdapter, stub_l6a: _StubL6A, baseline: Baseline
):
    """case.via=VIA_MEM 时 run_standard_compare 自动走 fallback。"""
    case = Case(case_id="c3", baseline=baseline, via=Via.VIA_MEM)
    # mem 比数：g_debugCnt=0 → 空批 → 0 diff
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
