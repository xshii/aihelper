import json
import pathlib

import pytest
from click.testing import CliRunner

from pa_debug.cli import main

pytestmark = pytest.mark.integration

ROOT = pathlib.Path(__file__).resolve().parents[2]
STUBS = ROOT / "stubs"
RULES_DIR = ROOT / "rules"
EX = ROOT / "examples"


def test_instrument_writes_outputs(tmp_path):
    src = tmp_path / "conv.c"
    src.write_text((EX / "conv.c").read_text())
    out_dir = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "instrument",
            str(src),
            "--stub-dir",
            str(STUBS),
            "--rules-dir",
            str(RULES_DIR),
            "--out-dir",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    inst = out_dir / "conv.c"
    sites = out_dir / "sites.json"
    assert inst.exists() and sites.exists()
    assert "pa_hook_before" in inst.read_text()
    assert json.loads(sites.read_text())[0]["op"] == "CONV"
