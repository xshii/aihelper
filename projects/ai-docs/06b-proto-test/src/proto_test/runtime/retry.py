"""声明式重试 — 详见 06b § 3.6.

入口：
- ``@retryable(max_retries, backoff_s)`` — 仅对 ``TransientError`` 自动重试
- ``total_backoff(max_retries, backoff_s)`` — 退避总时长，用于配 timeout 嵌套上限

约定：
- 只对 ``TransientError`` 重试；``HardwareFaultError`` / ``IllegalStateError`` 立即上抛
- 退避序列：``backoff, 2×backoff, 4×backoff, ...``（指数）
- 嵌套规则：上层 timeout 须 >= 下层 × 重试次数 + ``total_backoff``
"""
from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable, Optional, TypeVar

from ..foundation.errors import TransientError

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def retryable(max_retries: int = 3, backoff_s: float = 1.0) -> Callable[[F], F]:
    """装饰器：函数抛 ``TransientError`` 时自动重试。

    Args:
        max_retries: 最多重试次数（不含首次）。``3`` = 总共最多 4 次调用。
        backoff_s:   首次退避秒；后续指数翻倍。
    """
    if max_retries < 0:
        raise ValueError(f"max_retries 必须 >= 0，得到 {max_retries}")

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last: Optional[TransientError] = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except TransientError as e:
                    last = e
                    if attempt >= max_retries:
                        break
                    delay = backoff_s * (2 ** attempt)
                    logger.warning(
                        "%s: TransientError on attempt %d/%d, sleep %.2fs",
                        func.__qualname__, attempt + 1, max_retries + 1, delay,
                    )
                    time.sleep(delay)
            assert last is not None
            raise last

        return wrapper  # type: ignore[return-value]

    return decorator


def total_backoff(max_retries: int, backoff_s: float) -> float:
    """``retryable`` 最坏情况下的退避总时长（不含函数本身耗时）。"""
    if max_retries <= 0:
        return 0.0
    return sum(backoff_s * (2 ** i) for i in range(max_retries))
