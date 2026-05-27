"""CLI instrument-macros:第二级硬件宏就地插桩 + git 守卫(需 libclang + git)。"""

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from pa_debug.cli import main

pytestmark = pytest.mark.integration

HEADER = """typedef struct { unsigned opid; } commopheader;
#define hac_3r(w0, w1, w2) do { (void)(w0); (void)(w1); (void)(w2); } while (0)
static inline void pa_conv(commopheader* h, int ish) {
    hac_3r(1, ish, 0);
}
"""


def _committed_header(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=tmp_path, check=True)
    hdr = tmp_path / "intrinsics.h"
    hdr.write_text(HEADER)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    return hdr


def test_instruments_macros_in_place(tmp_path):
    hdr = _committed_header(tmp_path)
    result = CliRunner().invoke(
        main,
        [
            "instrument-macros",
            str(hdr),
            "--macro",
            "hac_3r",
            "--meta-dir",
            str(tmp_path / ".pa-debug"),
        ],
    )
    assert result.exit_code == 0, result.output
    text = hdr.read_text()
    assert "pa-debug:instrumented" in text
    assert "pa_dump_enabled" in text  # 门控 dump 已插入
    sites = json.loads((tmp_path / ".pa-debug" / "intrinsics.h.sites.json").read_text())
    assert sites[0]["kind"] == "macro"
    assert sites[0]["op"] == "hac_3r"
