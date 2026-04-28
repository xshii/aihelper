"""LifecycleFSM 单测."""
from __future__ import annotations

import logging

import pytest

from proto_test.errors import IllegalStateError
from proto_test.lifecycle import LifecycleEvent as Ev
from proto_test.lifecycle import LifecycleFSM, ModelState


def test_happy_path():
    fsm = LifecycleFSM()
    assert fsm.state == ModelState.IDLE
    fsm.transition(Ev.LOAD_DO)
    assert fsm.state == ModelState.LOADING
    fsm.transition(Ev.RAT_READY)
    assert fsm.state == ModelState.READY
    fsm.transition(Ev.START_MODEL)
    assert fsm.state == ModelState.RUNNING
    fsm.transition(Ev.RESULT_READY)
    assert fsm.state == ModelState.DONE


def test_illegal_transition_raises():
    fsm = LifecycleFSM()
    with pytest.raises(IllegalStateError, match="非法转移"):
        fsm.transition(Ev.START_MODEL)               # IDLE 不能直接 start


def test_retry_increments_count():
    fsm = LifecycleFSM()
    fsm.transition(Ev.LOAD_DO)                       # IDLE -> LOADING
    fsm.transition(Ev.RETRY)                         # LOADING -> LOADING
    fsm.transition(Ev.RETRY)
    assert fsm.retry_count == 2
    fsm.transition(Ev.RAT_READY)                     # 非 retry 事件清零
    assert fsm.retry_count == 0


def test_retry_count_preserved_in_log_on_fatal(caplog: pytest.LogCaptureFixture):
    """FATAL 转移时日志须保留进入此次转移前的累积重试次数（诊断不丢）。"""
    fsm = LifecycleFSM()
    fsm.transition(Ev.LOAD_DO)                       # IDLE -> LOADING
    fsm.transition(Ev.RETRY)
    fsm.transition(Ev.RETRY)
    with caplog.at_level(logging.INFO, logger="proto_test.lifecycle"):
        fsm.transition(Ev.FATAL)                     # LOADING -> ERROR
    fatal_log = [r for r in caplog.records if "Error" in r.getMessage()][-1]
    assert "retries=2" in fatal_log.getMessage()
    assert fsm.retry_count == 0


def test_retry_count_preserved_in_log_on_rat_ready(caplog: pytest.LogCaptureFixture):
    """RAT_READY 转移日志同样应保留累积次数（不在 reset 之后才 log）。"""
    fsm = LifecycleFSM()
    fsm.transition(Ev.LOAD_DO)
    fsm.transition(Ev.RETRY)
    fsm.transition(Ev.RETRY)
    fsm.transition(Ev.RETRY)
    with caplog.at_level(logging.INFO, logger="proto_test.lifecycle"):
        fsm.transition(Ev.RAT_READY)
    ready_log = [r for r in caplog.records if "Ready" in r.getMessage()][-1]
    assert "retries=3" in ready_log.getMessage()
    assert fsm.retry_count == 0


def test_error_recovery_via_hard_reset():
    fsm = LifecycleFSM()
    fsm.transition(Ev.LOAD_DO)
    fsm.transition(Ev.FATAL)
    assert fsm.state == ModelState.ERROR
    fsm.transition(Ev.HARD_RESET)
    assert fsm.state == ModelState.LOADING


def test_terminate_session():
    fsm = LifecycleFSM()
    fsm.transition(Ev.LOAD_DO)
    fsm.transition(Ev.FATAL)
    fsm.transition(Ev.GIVE_UP_SESSION)
    assert fsm.state == ModelState.TERMINATED


def test_switch_compare_allowed_in_idle():
    fsm = LifecycleFSM()
    fsm.require_switch_compare()                    # IDLE 允许，不抛


def test_switch_compare_denied_in_running():
    fsm = LifecycleFSM()
    fsm.transition(Ev.LOAD_DO)
    fsm.transition(Ev.RAT_READY)
    fsm.transition(Ev.START_MODEL)
    with pytest.raises(IllegalStateError):
        fsm.require_switch_compare()


def test_switch_compare_allowed_in_done():
    fsm = LifecycleFSM()
    fsm.transition(Ev.LOAD_DO)
    fsm.transition(Ev.RAT_READY)
    fsm.transition(Ev.START_MODEL)
    fsm.transition(Ev.RESULT_READY)
    fsm.require_switch_compare()                    # DONE 允许，不抛
