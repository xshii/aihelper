"""第二级:对头文件 inline 体内的硬件宏插桩 corpus(需 libclang)。

case 目录:tests/fixtures/macros/<case>/{input.h, expected.h, sites.json}
"""

import dataclasses
import json
import pathlib

import pytest

from pa_debug.l1_transformer.config import DiscoveryConfig
from pa_debug.l1_transformer.transformer import instrument_macros

pytestmark = pytest.mark.integration

FIX = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "macros"
CASES = sorted(p.name for p in FIX.iterdir() if (p / "input.h").exists())
CFG = DiscoveryConfig(intrinsic_headers=[], hardware_macros=["hac_2r", "hac_3r"])


def _run(case: str):
    return instrument_macros(str(FIX / case / "input.h"), CFG)


def _norm(text: str) -> list[str]:
    return [ln.rstrip() for ln in text.strip().splitlines()]


@pytest.mark.parametrize("case", CASES)
def test_instrumented_header_matches_expected(case):
    out, _ = _run(case)
    assert _norm(out) == _norm((FIX / case / "expected.h").read_text())


@pytest.mark.parametrize("case", CASES)
def test_macro_manifest_matches_sites_json(case):
    _, manifest = _run(case)
    got = [dataclasses.asdict(s) for s in manifest]
    assert got == json.loads((FIX / case / "sites.json").read_text())
