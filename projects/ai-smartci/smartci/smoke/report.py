"""冒烟 JSON 报告 dataclass + loader

契约：团队冒烟入口脚本退出前往 $SMARTCI_REPORT_PATH 写一份 JSON：
{
  "platform": "fpga",
  "passed": 12, "failed": 1, "skipped": 0,
  "duration_sec": 320,
  "cases": [
    {"name": "boot", "status": "pass", "duration_sec": 30},
    {"name": "dma_loopback", "status": "fail", "message": "timeout"}
  ]
}
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from smartci.const import CaseStatus  # noqa: F401  (导出给外部/测试用)


@dataclass(frozen=True)
class CaseResult:
    name: str
    status: str                         # "pass" / "fail" / "skip"
    duration_sec: Optional[float] = None
    message: Optional[str] = None


@dataclass
class SmokeReport:
    platform: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration_sec: float = 0.0
    cases: List[CaseResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.failed == 0

    @classmethod
    def load(cls, path: Path) -> "SmokeReport":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        cases = [CaseResult(**c) for c in data.get("cases", [])]
        return cls(
            platform=data["platform"],
            passed=data.get("passed", 0),
            failed=data.get("failed", 0),
            skipped=data.get("skipped", 0),
            duration_sec=data.get("duration_sec", 0.0),
            cases=cases,
        )
