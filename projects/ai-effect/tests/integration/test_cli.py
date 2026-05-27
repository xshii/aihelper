"""CLI instrument:就地改写 + git 守卫 + 幂等 marker。"""

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from pa_debug.cli import main

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
STUBS = ROOT / "stubs"
RULES_DIR = ROOT / "rules"
EX = ROOT / "examples"


def _committed_conv(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=tmp_path, check=True)
    src = tmp_path / "conv.c"
    src.write_text((EX / "conv.c").read_text())
    subprocess.run(["git", "add", "conv.c"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    return src


def _invoke(src: Path, tmp_path: Path, *extra: str):
    return CliRunner().invoke(
        main,
        [
            "instrument",
            str(src),
            "--stub-dir",
            str(STUBS),
            "--rules-dir",
            str(RULES_DIR),
            "--meta-dir",
            str(tmp_path / ".pa-debug"),
            *extra,
        ],
    )


def test_instruments_in_place_on_clean_file(tmp_path):
    src = _committed_conv(tmp_path)
    result = _invoke(src, tmp_path)
    assert result.exit_code == 0, result.output
    text = src.read_text()
    assert "pa_hook_before" in text
    assert "pa-debug:instrumented" in text
    sites = json.loads((tmp_path / ".pa-debug" / "conv.c.sites.json").read_text())
    assert sites[0]["op"] == "CONV"


def test_aborts_on_dirty_file(tmp_path):
    src = _committed_conv(tmp_path)
    src.write_text(src.read_text() + "// uncommitted edit\n")
    result = _invoke(src, tmp_path)
    assert result.exit_code != 0
    assert "pa_hook_before" not in src.read_text()  # 未被插桩


def test_allow_dirty_bypasses_guard(tmp_path):
    src = _committed_conv(tmp_path)
    src.write_text(src.read_text() + "// uncommitted edit\n")
    result = _invoke(src, tmp_path, "--allow-dirty")
    assert result.exit_code == 0, result.output
    assert "pa_hook_before" in src.read_text()


def test_refuses_double_instrumentation(tmp_path):
    src = _committed_conv(tmp_path)
    assert _invoke(src, tmp_path).exit_code == 0
    # 第二次用 --allow-dirty 排除 git 守卫,单独验证 marker 拦截
    result = _invoke(src, tmp_path, "--allow-dirty")
    assert result.exit_code != 0
    assert "已插桩" in result.output
