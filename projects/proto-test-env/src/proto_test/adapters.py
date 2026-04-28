"""平台适配器与机制 Strategy（详见 06b § 4.2 / § 4.4）.

入口：
- ``PlatformAdapter``   — 跨平台抽象端口（与 06 § 4 对齐）
- ``MemoryPort``        — DummyAdapter 的字节级 bytearray 端口
- ``DummyAdapter``      — 纯内存平台，跑契约 / meta-test 用
- ``L6APort``           — 接口 FPGA 软调 SDK 抽象（机制 A 物理底座）
- ``Mechanism``         — A/B Strategy 接口
- ``MessageMechanism``  — 机制 A：VPORT 消息 + 接口 FPGA 比数引擎
- ``MemoryMechanism``   — 机制 B：SoftDebug + 桩 CPU 软比
- ``FpgaAdapter``       — 实现 PlatformAdapter；按 ``case.via`` 分发到 A/B

约定：
- 与 ``compare.MemoryCompareDriver`` 协作完成机制 B 比数（§ 1.6 协议）
- 与 ``lifecycle.LifecycleFSM`` 协作做状态推进
- ``MemPort``（字节级端口）复用自 ``memory`` 模块；不再单独定义 L6BPort
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, Protocol, runtime_checkable

from .compare import MemoryCompareDriver, run_compare_round
from .domain import Case, ResultOut, Via
from .lifecycle import LifecycleEvent, LifecycleFSM
from .memory import EndianStr, MemAccessAPI, MemPort, SymbolMap


# region PlatformAdapter Protocol ───────────────────────────────────
@runtime_checkable
class PlatformAdapter(Protocol):
    """跨平台适配器（详见 06 § 4 PlatformAdapter）。"""

    def load_version(self, baseline: Dict[str, Any]) -> None: ...
    def start_business(self, case: Case, payload: bytes = b"") -> None: ...
    def run_standard_compare(self, case: Case, golden: Any) -> ResultOut: ...
    def run_fallback_compare(self, case: Case, golden: Any) -> ResultOut: ...
# endregion


# region DummyAdapter — 给单测用 ──────────────────────────────────
class MemoryPort:
    """裸 ``bytearray`` 当 DUT，给 DummyAdapter 用；满足 ``MemPort`` Protocol。"""

    def __init__(self, size: int = 1 << 20):
        self._mem = bytearray(size)

    def read(self, addr: int, n: int) -> bytes:
        self._check_range(addr, n, "read")
        return bytes(self._mem[addr:addr + n])

    def write(self, addr: int, raw: bytes) -> None:
        self._check_range(addr, len(raw), "write")
        self._mem[addr:addr + len(raw)] = raw

    def _check_range(self, addr: int, n: int, op: str) -> None:
        if addr < 0 or addr + n > len(self._mem):
            raise IndexError(
                f"{op} out of range: addr=0x{addr:x}, n={n}, mem={len(self._mem)}"
            )

    @property
    def backing(self) -> bytearray:
        return self._mem


@dataclass
class DummyAdapter:
    """纯内存平台 — 契约 / meta-test 用，不依赖任何硬件。"""

    mem_size: int = 1 << 20
    endian: EndianStr = "<"
    _port: MemoryPort = field(init=False)
    _symbols: SymbolMap = field(init=False)
    mem: MemAccessAPI = field(init=False)

    def __post_init__(self) -> None:
        self._port = MemoryPort(self.mem_size)
        self._symbols = SymbolMap(table={})
        self.mem = MemAccessAPI(self._port, self._symbols, endian=self.endian)

    def install_symbol(self, name: str, addr: int) -> None:
        self._symbols.table[name] = addr

    def write_raw(self, addr: int, raw: bytes) -> None:
        self._port.write(addr, raw)

    def read_raw(self, addr: int, n: int) -> bytes:
        return self._port.read(addr, n)

    @property
    def backing(self) -> bytearray:
        return self._port.backing

    # PlatformAdapter 钩子（占位，便于 isinstance 检查）
    def load_version(self, baseline: Dict[str, Any]) -> None:
        return None

    def start_business(self, case: Case, payload: bytes = b"") -> None:
        return None

    def run_standard_compare(self, case: Case, golden: Any = None) -> ResultOut:
        return ResultOut()

    def run_fallback_compare(self, case: Case, golden: Any = None) -> ResultOut:
        return ResultOut()
# endregion


# region 机制 Strategy ──────────────────────────────────────────────
class Mechanism(Protocol):
    """A / B 共同 Strategy 接口（与 06b § 4.2 ``mechanism_ops_t`` 对齐）。"""

    def data_to_chip(self, case: Case, payload: bytes) -> None: ...
    def start_model(self, case: Case) -> None: ...
    def wait_result(self, case: Case, timeout_s: float = 30.0) -> ResultOut: ...
    def run_compare(self, case: Case, golden: Dict[Any, bytes]) -> ResultOut: ...


class L6APort(Protocol):
    """接口 FPGA 软调 SDK 抽象（详见 06b § 1.5）。"""

    def data_buf_write(self, raw: bytes) -> None: ...
    def cfg_timer(self, period_us: int) -> None: ...
    def msg_send_start(self) -> None: ...
    def msg_poll_done(self, timeout_s: float) -> bool: ...
    def cmp_engine_pull(self) -> ResultOut: ...


@dataclass
class MessageMechanism:
    """机制 A：通过 L6A SDK 走接口 FPGA 软调。"""

    l6a: L6APort
    timer_period_us: int = 100

    def data_to_chip(self, case: Case, payload: bytes) -> None:
        self.l6a.data_buf_write(payload)
        self.l6a.cfg_timer(self.timer_period_us)

    def start_model(self, case: Case) -> None:
        self.l6a.msg_send_start()

    def wait_result(self, case: Case, timeout_s: float = 30.0) -> ResultOut:
        ok = self.l6a.msg_poll_done(timeout_s)
        if not ok:
            return ResultOut(raw_status=1, elapsed_ms=int(timeout_s * 1000))
        return ResultOut(raw_status=0)

    def run_compare(self, case: Case, golden: Dict[Any, bytes]) -> ResultOut:
        return self.l6a.cmp_engine_pull()


@dataclass
class MemoryMechanism:
    """机制 B：通过 ``MemAccessAPI`` 走 SoftDebug。复用 ``compare.MemoryCompareDriver``。

    DUT 配置区内部布局（占位 — 真实由 DUT 链接脚本 / 协议文档约定）::

        cfg_region_base + 0                 启动字 (写 START_WORD = "go")
        cfg_region_base + STATUS_OFFSET     状态字 (== STATUS_DONE 表示完成)
        cfg_region_base + DATA_OFFSET       数据区起始
    """

    # ─── 协议契约常量（占位，待 Q-009 定型）──────────────
    DATA_OFFSET: ClassVar[int] = 0x100              # 数据区相对基址偏移
    STATUS_OFFSET: ClassVar[int] = 0x10             # 状态字相对基址偏移
    START_WORD: ClassVar[bytes] = b"\x01\x00\x00\x00"   # 写启动字 = 启动
    STATUS_DONE: ClassVar[int] = 1                  # 状态值 == 1 表示完成
    STATUS_BYTES: ClassVar[int] = 4                 # 状态字字节宽度

    mem: MemAccessAPI
    cfg_region_base: int = 0x2000
    poll_interval_s: float = 0.01

    def data_to_chip(self, case: Case, payload: bytes) -> None:
        self.mem.WriteBytes(self.cfg_region_base + self.DATA_OFFSET, payload)

    def start_model(self, case: Case) -> None:
        self.mem.WriteBytes(self.cfg_region_base, self.START_WORD)

    def wait_result(self, case: Case, timeout_s: float = 30.0) -> ResultOut:
        deadline = time.monotonic() + timeout_s
        polls = 0
        while time.monotonic() < deadline:
            polls += 1
            status_raw = self.mem.ReadBytes(
                self.cfg_region_base + self.STATUS_OFFSET, self.STATUS_BYTES
            )
            if int.from_bytes(status_raw, "little") == self.STATUS_DONE:
                return ResultOut(raw_status=0, poll_count=polls)
            time.sleep(self.poll_interval_s)
        return ResultOut(raw_status=1, poll_count=polls,
                         elapsed_ms=int(timeout_s * 1000))

    def run_compare(self, case: Case, golden: Dict[Any, bytes]) -> ResultOut:
        drv = MemoryCompareDriver(mem=self.mem)
        results = run_compare_round(drv, golden)
        return ResultOut(cmp_diff_count=sum(r.diff_bytes for r in results))
# endregion


# region FpgaAdapter ────────────────────────────────────────────────
@dataclass
class FpgaAdapter:
    """FPGA 平台适配器；按 ``case.via`` 选择 A / B 机制。"""

    mech_msg: MessageMechanism
    mech_mem: MemoryMechanism
    default_via: Via = Via.VIA_MSG
    fsm: LifecycleFSM = field(default_factory=LifecycleFSM)

    def _dispatch(self, case: Case) -> Mechanism:
        via = case.via or self.default_via
        return self.mech_msg if via == Via.VIA_MSG else self.mech_mem

    def load_version(self, baseline: Dict[str, Any]) -> None:
        """加载基线 — 简化实现：仅推动 FSM 到 READY。"""
        self.fsm.transition(LifecycleEvent.LOAD_DO)
        self.fsm.transition(LifecycleEvent.RAT_READY)

    def start_business(self, case: Case, payload: bytes = b"") -> None:
        mech = self._dispatch(case)
        mech.data_to_chip(case, payload)
        self.fsm.transition(LifecycleEvent.START_MODEL)
        mech.start_model(case)

    def wait_result(self, case: Case, timeout_s: float = 30.0) -> ResultOut:
        result = self._dispatch(case).wait_result(case, timeout_s)
        self.fsm.transition(
            LifecycleEvent.RESULT_READY if result.raw_status == 0
            else LifecycleEvent.FATAL
        )
        return result

    def run_standard_compare(self, case: Case, golden: Any = None) -> ResultOut:
        """标准路径仅机制 A；机制 B 自动落到 fallback。"""
        if (case.via or self.default_via) == Via.VIA_MEM:
            return self.run_fallback_compare(case, golden)
        return self.mech_msg.run_compare(case, golden or {})

    def run_fallback_compare(self, case: Case, golden: Any = None) -> ResultOut:
        return self.mech_mem.run_compare(case, golden or {})
# endregion
