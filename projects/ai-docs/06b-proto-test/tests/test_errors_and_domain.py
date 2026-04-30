"""errors.py + domain.py 单测."""
from __future__ import annotations

import pytest

from proto_test.domain import (
    Baseline, Case, CompareMode, ComparePath, HpTrigger,
    ResultOut, Verdict, Via,
)
from proto_test.errors import (
    AutotestError, AutotestTimeoutError, CommError,
    DataIntegrityError, HardwareFaultError, IllegalStateError,
    StubCpuError, TransientError, code_to_exception,
    ERR_OK, ERR_TIMEOUT_TRANSIENT,
)


# region errors ─────────────────────────────────────────────────────
def test_code_to_exception_band_mapping():
    assert isinstance(code_to_exception(0x1001), CommError)
    assert isinstance(code_to_exception(0x2999), AutotestTimeoutError)
    assert isinstance(code_to_exception(0x3001), IllegalStateError)
    assert isinstance(code_to_exception(0x4001), DataIntegrityError)
    assert isinstance(code_to_exception(0x5001), StubCpuError)
    assert isinstance(code_to_exception(0x6001), HardwareFaultError)


def test_transient_special_code():
    """ERR_TIMEOUT_TRANSIENT 必须翻译成 TransientError（可重试）。"""
    e = code_to_exception(ERR_TIMEOUT_TRANSIENT)
    assert isinstance(e, TransientError)
    assert isinstance(e, AutotestTimeoutError)            # 是子类


def test_err_ok_rejected():
    with pytest.raises(ValueError):
        code_to_exception(ERR_OK)


def test_exception_carries_context():
    e = AutotestError("oops", code=0x1234, context={"who": "me"})
    assert e.code == 0x1234
    assert e.context == {"who": "me"}
    assert "oops" in str(e)


def test_unknown_band_falls_to_base():
    e = code_to_exception(0x7000)
    assert type(e) is AutotestError
# endregion


# region domain ─────────────────────────────────────────────────────
def test_verdict_enum_values():
    assert Verdict.PASS.value == "PASS"
    assert Verdict.WARN.value == "WARN"
    assert Verdict.FAIL.value == "FAIL"


def test_result_out_to_verdict_pass():
    r = ResultOut()
    assert r.to_verdict() == Verdict.PASS


def test_result_out_to_verdict_diff_fail():
    r = ResultOut(cmp_diff_count=5)
    assert r.to_verdict() == Verdict.FAIL


def test_result_out_to_verdict_dfx_fail():
    r = ResultOut(dfx_alarm_mask=0x1)
    assert r.to_verdict() == Verdict.FAIL


def test_result_out_to_verdict_status_fail():
    r = ResultOut(raw_status=1)
    assert r.to_verdict() == Verdict.FAIL


def test_case_dataclass_defaults():
    bl = Baseline(image="img", do_path="do", golden_dir="g", gc_version="v1")
    c = Case(case_id="c1", baseline=bl)
    assert c.compare_mode == CompareMode.END_TO_END
    assert c.compare_path == ComparePath.STANDARD
    assert c.hp_trigger == HpTrigger.ON_FAIL
    assert c.via is None
    # frozen
    with pytest.raises((AttributeError, Exception)):
        c.case_id = "c2"                                    # type: ignore[misc]


def test_via_distinct_values():
    assert Via.VIA_MSG != Via.VIA_MEM
# endregion
