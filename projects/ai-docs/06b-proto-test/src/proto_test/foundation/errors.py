"""统一错误体系 — 详见 06b § 3.6 / § 4.5.

异常树（含错误码段位）::

    AutotestError                  — 基类（所有异常都带 code / context）
    ├── CommError                  0x1xxx  通信错误
    ├── AutotestTimeoutError       0x2xxx  超时
    │   └── TransientError                 可重试子类
    ├── IllegalStateError          0x3xxx  非法状态（编码 bug，不重试）
    ├── DataIntegrityError         0x4xxx  数据完整性（CRC / 大小不匹配）
    │   └── SymbolNotFoundError    0x4100  符号未在当前 image map 中
    ├── StubCpuError               0x5xxx  桩 CPU 内部
    └── HardwareFaultError         0x6xxx  硬件故障（fatal，不重试）

约定：
- ``@retryable`` 仅对 ``TransientError`` 自动重试
- 错误码段位与 errors.yaml 对齐；细分见 [Q-012]
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class AutotestError(Exception):
    """所有 Autotest 异常基类。"""

    def __init__(
        self,
        message: str,
        *,
        code: int = 0,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.context = context or {}

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code=0x{self.code:04x}, msg={self.args[0]!r})"


class CommError(AutotestError):
    """通信错误（DEBUG 口、SoftDebug 通道）；段位 0x1xxx。"""


class AutotestTimeoutError(AutotestError):
    """超时基类；段位 0x2xxx。"""


class TransientError(AutotestTimeoutError):
    """瞬态可恢复错误；``@retryable`` 自动重试。"""


class IllegalStateError(AutotestError):
    """状态机非法转移；段位 0x3xxx。**编码 bug，不重试。**"""


class DataIntegrityError(AutotestError):
    """数据校验失败（CRC / 大小不匹配 / 字节数不符）；段位 0x4xxx。"""


class SymbolNotFoundError(DataIntegrityError):
    """符号未在当前 image 的 map 中；属 0x4xxx 数据完整性段位（``ERR_SYMBOL_NOT_FOUND = 0x4100``）。"""


class StubCpuError(AutotestError):
    """桩 CPU 内部错误；段位 0x5xxx。"""


class HardwareFaultError(AutotestError):
    """硬件故障；段位 0x6xxx；**fatal**，不重试。"""


# region 错误码段位常量 ─────────────────────────────────────────────
ERR_OK                       = 0x0000
ERR_COMM_BASE                = 0x1000
ERR_TIMEOUT_BASE             = 0x2000
ERR_TIMEOUT_TRANSIENT        = 0x2001  # 网络抖动 / 单次重传
ERR_ILLEGAL_STATE_BASE       = 0x3000
ERR_ILLEGAL_TRANSITION       = 0x3000  # FSM 非法转移
ERR_SWITCH_COMPARE_DENIED    = 0x3001  # 比数模式 / 路径切换被状态守卫拒绝
ERR_DATA_INTEGRITY_BASE      = 0x4000
ERR_DATA_CRC_MISMATCH        = 0x4001
ERR_COMPARE_BUF_OVERFLOW     = 0x4002
ERR_SYMBOL_NOT_FOUND         = 0x4100
ERR_BUFFER_REGISTRY_FULL     = 0x4200
ERR_STUB_CPU_BASE            = 0x5000
ERR_HARDWARE_FAULT_BASE      = 0x6000
# endregion


_BAND_TO_CLASS = {
    0x1000: CommError,
    0x2000: AutotestTimeoutError,
    0x3000: IllegalStateError,
    0x4000: DataIntegrityError,
    0x5000: StubCpuError,
    0x6000: HardwareFaultError,
}


def code_to_exception(code: int, message: str = "", **context: Any) -> AutotestError:
    """L3 通信层做错误码 → 异常翻译；详见 06b § 3.6。

    特殊：``code == ERR_TIMEOUT_TRANSIENT`` 翻译为 ``TransientError``（可重试）。
    """
    if code == ERR_OK:
        raise ValueError("ERR_OK 不应翻译为异常")
    if code == ERR_TIMEOUT_TRANSIENT:
        return TransientError(message or f"transient timeout 0x{code:04x}",
                              code=code, context=context)
    band = code & 0xF000
    cls = _BAND_TO_CLASS.get(band, AutotestError)
    return cls(message or f"code=0x{code:04x}", code=code, context=context)
