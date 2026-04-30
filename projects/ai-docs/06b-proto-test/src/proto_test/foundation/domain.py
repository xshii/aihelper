"""核心域对象 — Enums / dataclasses（详见 06b § 4.3 / § 4.6）.

入口：
- ``Verdict``         — {PASS, WARN, FAIL}（03 § 5.1）
- ``CompareMode``     — {END_TO_END, STAGE_COMPARE}（02 § 1.1）
- ``ComparePath``     — {STANDARD, FALLBACK}（02 § 4.1）
- ``HpTrigger``       — {OFF, ON_FAIL, ALWAYS}
- ``SwitchStrategy``  — {SOFT, MEDIUM, HARD}（06 切换钩子）
- ``Via``             — {VIA_MSG, VIA_MEM} 机制选择
- ``Baseline``        — 版本基线 (image / DO / golden / gc_version)（03 § 2.2）
- ``Stage``           — 阶段性比数张量阶段（02 § 1.2）
- ``Case``            — 测试用例
- ``ResultOut``       — A/B 共用返回结构（§ 4.6 ``result_out_t``）

约定：
- 所有 dataclass 默认 ``frozen=True``（``ResultOut`` 例外，用作可变累加器）
- Enums 值用 str，方便 JSON / YAML 互转
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


class Verdict(Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class CompareMode(Enum):
    END_TO_END = "END_TO_END"
    STAGE_COMPARE = "STAGE_COMPARE"


class ComparePath(Enum):
    STANDARD = "STANDARD"
    FALLBACK = "FALLBACK"


class HpTrigger(Enum):
    OFF = "OFF"
    ON_FAIL = "ON_FAIL"
    ALWAYS = "ALWAYS"


class SwitchStrategy(Enum):
    SOFT = "SOFT"           # 仅切换业务上下文
    MEDIUM = "MEDIUM"       # 切换业务软件，保留 FPGA 配置
    HARD = "HARD"           # 完整硬复位


class Via(Enum):
    VIA_MSG = "VIA_MSG"     # 机制 A
    VIA_MEM = "VIA_MEM"     # 机制 B


@dataclass(frozen=True)
class Baseline:
    """版本基线 — 用例运行的不变锚点（03 § 2.2）。"""

    image: str
    do_path: str
    golden_dir: str
    gc_version: str


@dataclass(frozen=True)
class Stage:
    """阶段性比数张量阶段（02 § 1.2）。"""

    tid: int
    cnt: int = 0


@dataclass(frozen=True)
class Case:
    """测试用例描述（输入 + 期望）。"""

    case_id: str
    baseline: Baseline
    stages: Tuple[Stage, ...] = field(default_factory=tuple)
    compare_mode: CompareMode = CompareMode.END_TO_END
    compare_path: ComparePath = ComparePath.STANDARD
    hp_trigger: HpTrigger = HpTrigger.ON_FAIL
    via: Optional[Via] = None       # None = adapter 默认


@dataclass
class ResultOut:
    """A / B 机制共用返回结构（§ 4.6 ``result_out_t``）。

    L2 据此翻译 ``Verdict``（规则见 03 § 5.2）。
    """

    raw_status: int = 0
    cmp_diff_count: int = 0
    perf_metric: int = 0
    dfx_alarm_mask: int = 0
    elapsed_ms: int = 0
    poll_count: int = 0

    def to_verdict(self) -> Verdict:
        """L2 翻译规则（03 § 5.2 简化版）::

            dfx_alarm_mask != 0   → FAIL
            cmp_diff_count > 0    → FAIL
            raw_status != 0       → FAIL（如 wait_result 超时）
            其它                  → PASS

        WARN 维度（性能边界 / 警戒区）此处未编码，由用例策略附加。
        """
        if self.dfx_alarm_mask != 0:
            return Verdict.FAIL
        if self.cmp_diff_count > 0:
            return Verdict.FAIL
        if self.raw_status != 0:
            return Verdict.FAIL
        return Verdict.PASS
