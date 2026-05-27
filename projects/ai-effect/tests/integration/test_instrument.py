"""端到端插桩 corpus:每个 case 目录测一个行为(需 libclang)。

case 目录:tests/fixtures/instrument/<case>/{input.c, expected.c, sites.json}
共用头 intrinsics.h 在 fixtures 根,经 -I 引入。
"""

import dataclasses
import json
import pathlib

import pytest

from pa_debug.l1_transformer.config import DiscoveryConfig
from pa_debug.l1_transformer.transformer import instrument

pytestmark = pytest.mark.integration

FIX = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "instrument"
CASES = sorted(p.name for p in FIX.iterdir() if (p / "input.c").exists())
CFG = DiscoveryConfig(intrinsic_headers=["intrinsics.h"], deny=[r"^_"])


def _run(case: str):
    return instrument(str(FIX / case / "input.c"), CFG, clang_args=["-I", str(FIX)])


def _norm(text: str) -> list[str]:
    return [ln.rstrip() for ln in text.strip().splitlines()]


@pytest.mark.parametrize("case", CASES)
def test_instrumented_source_matches_expected(case):
    out, _ = _run(case)
    assert _norm(out) == _norm((FIX / case / "expected.c").read_text())


@pytest.mark.parametrize("case", CASES)
def test_manifest_matches_sites_json(case):
    _, manifest = _run(case)
    got = [dataclasses.asdict(s) for s in manifest]
    assert got == json.loads((FIX / case / "sites.json").read_text())
