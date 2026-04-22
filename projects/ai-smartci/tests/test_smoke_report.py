"""SmokeReport.load 与 dataclass 行为"""

from __future__ import annotations

from smartci.smoke.report import CaseResult, SmokeReport


def test_smoke_report_load_from_json(tmp_path, fixture_dir):
    data = (fixture_dir / "report.sample.json").read_text(encoding="utf-8")
    path = tmp_path / "r.json"
    path.write_text(data, encoding="utf-8")
    rpt = SmokeReport.load(path)
    assert rpt.platform == "fpga"
    assert rpt.passed == 2 and rpt.failed == 1
    assert not rpt.ok
    assert len(rpt.cases) == 3
    assert rpt.cases[1] == CaseResult(
        name="dma_loopback", status="fail",
        duration_sec=5.0, message="timeout",
    )


def test_smoke_report_ok_when_no_failures():
    rpt = SmokeReport(platform="emu", passed=5, failed=0)
    assert rpt.ok
