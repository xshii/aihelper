"""机制 B 比数协议 — § 1.6 ``g_debugCnt`` + ``g_compAddr[200]`` 实现.

入口：
- ``MemoryCompareDriver``  — L5B 内存比数驱动；封装轮询契约
- ``pull_compare_batch()`` — 拉一批比数描述符 + 对应数据；空批返回 ``[]``
- ``clear_compare_buf()``  — 显式清零（异常恢复路径用）
- ``soft_compare()``       — 张量软比；返回 ``CompareResult``

设计点：
- DUT 固件维护 ``g_debugCnt`` (uint32) + ``g_compAddr[200]`` (CompareEntry[])
- 桩 CPU 走 SoftDebug 通过 ``MemAccessAPI`` 读这两个符号 → 软比 → 写 0
- 同 ``tid`` 多次产出用 ``cnt`` 区分；GOLDEN 按 ``(tid, cnt)`` 二维索引

错误：
- ``g_debugCnt > MAX_ENTRIES`` → ``CompareBufOverflow``（固件应同时触发 DFX 告警）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .errors import AutotestError, ERR_COMPARE_BUF_OVERFLOW
from .memory import CompareEntry, Datatype, MemAccessAPI

MAX_ENTRIES = 200

# ─── DUT 固件链接契约 — 与 dut/compare_buf.h 对齐 ──────────
SYM_DEBUG_CNT = "g_debugCnt"
SYM_COMP_ADDR = "g_compAddr"


CompareEntryDict = Dict[str, int]                  # {"tid", "cnt", "length", "addr"}
CompareBatchEntry = Tuple[CompareEntryDict, bytes]  # (描述符, 张量数据)


class CompareBufOverflow(AutotestError):
    """``g_debugCnt`` 超过 200 —— 固件应同时触发 DFX 告警；段位 0x4002。"""


@dataclass
class CompareResult:
    """单条比数结果。"""

    tid: int
    cnt: int
    diff_bytes: int     # 不同字节数；0 = PASS
    length: int

    @property
    def passed(self) -> bool:
        return self.diff_bytes == 0


@dataclass
class MemoryCompareDriver:
    """L5B 内存比数驱动（§ 1.6.4）。"""

    mem: MemAccessAPI

    def pull_compare_batch(self) -> List[CompareBatchEntry]:
        """轮询一次：读 ``g_debugCnt`` → 读 N 条描述符 → 拉每条数据。

        空批（``g_debugCnt == 0``）返回 ``[]``，不写清零。
        非空批返回后**调用方负责** ``clear_compare_buf()``。
        """
        n = self.mem.ReadVal(SYM_DEBUG_CNT, Datatype.UINT32)
        if n == 0:
            return []
        if n > MAX_ENTRIES:
            raise CompareBufOverflow(
                f"g_debugCnt={n} 超过容量 {MAX_ENTRIES}；固件应触发 DFX 告警",
                code=ERR_COMPARE_BUF_OVERFLOW,
            )
        batch: List[CompareBatchEntry] = []
        for i in range(1, n + 1):                      # 1-based
            entry = self.mem.ReadStruct(SYM_COMP_ADDR, CompareEntry, i)
            data = self.mem.ReadBytes(entry["addr"], entry["length"])
            batch.append((entry, data))
        return batch

    def clear_compare_buf(self) -> None:
        """整体清零；固件视为已消费。"""
        self.mem.WriteVal(SYM_DEBUG_CNT, Datatype.UINT32, 0)


def soft_compare(
    entry: CompareEntryDict, actual: bytes, golden: bytes
) -> CompareResult:
    """逐字节软比；返回不同字节数。"""
    length = entry["length"]
    if len(actual) != length or len(golden) != length:
        diff = max(len(actual), len(golden))
    else:
        diff = sum(1 for a, g in zip(actual, golden) if a != g)
    return CompareResult(
        tid=entry["tid"],
        cnt=entry["cnt"],
        diff_bytes=diff,
        length=length,
    )


def run_compare_round(
    drv: MemoryCompareDriver, golden: Dict[Tuple[int, int], bytes]
) -> List[CompareResult]:
    """完整一轮：拉 batch → 逐条软比 → 清零；返回所有结果。

    Golden 按 ``(tid, cnt)`` 二维索引（同 tid 多次产出场景）。
    """
    batch = drv.pull_compare_batch()
    if not batch:
        return []
    results: List[CompareResult] = []
    for entry, data in batch:
        key = (entry["tid"], entry["cnt"])
        gold = golden.get(key, b"")
        results.append(soft_compare(entry, data, gold))
    drv.clear_compare_buf()
    return results
