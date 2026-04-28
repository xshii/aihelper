"""模型生命周期 FSM M06 — 详见 06b § 2.7 / § 3.5.

入口：
- ``ModelState``      — Idle / Loading / Ready / Running / Done / Error / Terminated
- ``LifecycleEvent``  — 11 种合法事件 enum（替代魔鬼字符串）
- ``LifecycleFSM``    — 状态机；非法转移抛 ``IllegalStateError``

约定：
- 任何状态变更必须打日志 ``STATE: A -> B (took {ms}, retries={n})``
- ``switch_compare_mode`` / ``switch_compare_path`` 仅在 Idle / Done / Ready 允许
- ``Error -> Loading`` 由 ``HARD_RESET`` 触发，恢复后从 Loading 重入
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, Tuple

from .errors import (
    ERR_ILLEGAL_TRANSITION,
    ERR_SWITCH_COMPARE_DENIED,
    IllegalStateError,
)

logger = logging.getLogger(__name__)


class ModelState(Enum):
    IDLE = "Idle"
    LOADING = "Loading"
    READY = "Ready"
    RUNNING = "Running"
    DONE = "Done"
    ERROR = "Error"
    TERMINATED = "Terminated"


class LifecycleEvent(Enum):
    """FSM 转移事件枚举（替代字符串字面量）。"""

    LOAD_DO = "load_do"
    RAT_READY = "rat_ready"
    RETRY = "retry"
    FATAL = "fatal"
    START_MODEL = "start_model"
    RESULT_READY = "result_ready"
    CLEANUP = "cleanup"
    SWITCH_MODEL = "switch_model"
    HARD_RESET = "hard_reset"
    GIVE_UP = "give_up"
    GIVE_UP_SESSION = "give_up_session"


# 合法转移表：(from_state, event) -> to_state
_TRANSITIONS: Dict[Tuple[ModelState, LifecycleEvent], ModelState] = {
    (ModelState.IDLE,    LifecycleEvent.LOAD_DO):          ModelState.LOADING,
    (ModelState.LOADING, LifecycleEvent.RAT_READY):        ModelState.READY,
    (ModelState.LOADING, LifecycleEvent.RETRY):            ModelState.LOADING,
    (ModelState.LOADING, LifecycleEvent.FATAL):            ModelState.ERROR,
    (ModelState.READY,   LifecycleEvent.START_MODEL):      ModelState.RUNNING,
    (ModelState.RUNNING, LifecycleEvent.RESULT_READY):     ModelState.DONE,
    (ModelState.RUNNING, LifecycleEvent.FATAL):            ModelState.ERROR,
    (ModelState.DONE,    LifecycleEvent.CLEANUP):          ModelState.IDLE,
    (ModelState.DONE,    LifecycleEvent.SWITCH_MODEL):     ModelState.LOADING,
    (ModelState.ERROR,   LifecycleEvent.HARD_RESET):       ModelState.LOADING,
    (ModelState.ERROR,   LifecycleEvent.GIVE_UP):          ModelState.IDLE,
    (ModelState.ERROR,   LifecycleEvent.GIVE_UP_SESSION):  ModelState.TERMINATED,
}

# 比数模式 / 路径切换允许的状态（§ 2.7 / § 3.4）
_SWITCH_COMPARE_ALLOWED: FrozenSet[ModelState] = frozenset(
    {ModelState.IDLE, ModelState.DONE, ModelState.READY}
)


@dataclass
class LifecycleFSM:
    """模型生命周期状态机；线程不安全，调用方负责串行化。"""

    state: ModelState = ModelState.IDLE
    retry_count: int = 0
    _entered_ts: float = field(default_factory=time.monotonic, init=False)

    def transition(self, event: LifecycleEvent) -> ModelState:
        """触发转移；非法转移抛 ``IllegalStateError``。

        ``retry_count`` 日志保留**进入此次转移时累积的次数**（FATAL / RAT_READY
        等转出 LOADING 时仍能看到此前重试了几次），转移完成后再清零。
        """
        key = (self.state, event)
        if key not in _TRANSITIONS:
            raise IllegalStateError(
                f"非法转移: {self.state.value} --[{event.value}]--> ?",
                code=ERR_ILLEGAL_TRANSITION,
                context={"state": self.state.value, "event": event.value},
            )
        next_state = _TRANSITIONS[key]
        elapsed_ms = int((time.monotonic() - self._entered_ts) * 1000)

        if event is LifecycleEvent.RETRY:
            self.retry_count += 1

        # 先 log（含累积 retry 次数），再决定是否重置
        logger.info(
            "STATE: %s -> %s (took %dms, retries=%d)",
            self.state.value, next_state.value, elapsed_ms, self.retry_count,
        )

        if event is not LifecycleEvent.RETRY:
            self.retry_count = 0

        self.state = next_state
        self._entered_ts = time.monotonic()
        return next_state

    def require_switch_compare(self) -> None:
        """切比数模式 / 路径前的状态守卫；非 Idle/Done/Ready 抛 ``IllegalStateError``。"""
        if self.state not in _SWITCH_COMPARE_ALLOWED:
            raise IllegalStateError(
                f"switch_compare 仅在 Idle/Done/Ready 允许；当前 {self.state.value}",
                code=ERR_SWITCH_COMPARE_DENIED,
                context={"state": self.state.value},
            )
