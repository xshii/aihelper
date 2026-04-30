"""@retryable 装饰器单测."""
from __future__ import annotations

import time

import pytest

from proto_test.foundation.errors import (
    DataIntegrityError, HardwareFaultError, TransientError,
)
from proto_test.runtime.retry import retryable, total_backoff


def test_retryable_first_success():
    calls = {"n": 0}

    @retryable(max_retries=3, backoff_s=0.001)
    def f() -> int:
        calls["n"] += 1
        return 42

    assert f() == 42
    assert calls["n"] == 1


def test_retryable_recovers_after_transient():
    calls = {"n": 0}

    @retryable(max_retries=3, backoff_s=0.001)
    def f() -> int:
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientError("flaky", code=0x2001)
        return "ok"

    assert f() == "ok"
    assert calls["n"] == 3


def test_retryable_gives_up_after_max():
    calls = {"n": 0}

    @retryable(max_retries=2, backoff_s=0.001)
    def f() -> None:
        calls["n"] += 1
        raise TransientError("always fails", code=0x2001)

    with pytest.raises(TransientError):
        f()
    assert calls["n"] == 3                          # 1 首次 + 2 retry


def test_retryable_does_not_retry_non_transient():
    calls = {"n": 0}

    @retryable(max_retries=5, backoff_s=0.001)
    def f() -> None:
        calls["n"] += 1
        raise DataIntegrityError("bad crc", code=0x4001)

    with pytest.raises(DataIntegrityError):
        f()
    assert calls["n"] == 1                          # 不重试


def test_retryable_does_not_retry_hardware_fault():
    calls = {"n": 0}

    @retryable(max_retries=5, backoff_s=0.001)
    def f() -> None:
        calls["n"] += 1
        raise HardwareFaultError("hw fail", code=0x6001)

    with pytest.raises(HardwareFaultError):
        f()
    assert calls["n"] == 1


def test_retryable_negative_max_rejected():
    with pytest.raises(ValueError):
        retryable(max_retries=-1)                   # type: ignore[arg-type]


def test_total_backoff_geometric():
    # backoff=1, max=3 → 1 + 2 + 4 = 7
    assert total_backoff(3, 1.0) == 7.0
    # backoff=0.5, max=4 → 0.5 + 1 + 2 + 4 = 7.5
    assert total_backoff(4, 0.5) == 7.5
    assert total_backoff(0, 1.0) == 0.0


def test_retryable_actual_sleeps_minimal():
    """退避序列存在但用 0.001s 跑得很快，避免拖慢 CI。"""
    @retryable(max_retries=2, backoff_s=0.001)
    def f() -> None:
        raise TransientError("e", code=0x2001)

    t0 = time.monotonic()
    with pytest.raises(TransientError):
        f()
    elapsed = time.monotonic() - t0
    assert elapsed < 1.0                            # 充分宽松
