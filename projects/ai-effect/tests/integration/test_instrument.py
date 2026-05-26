"""端到端插桩:fixture corpus 驱动。每个 case 目录测一个行为。

case 目录约定:tests/fixtures/instrument/<case>/
  input.c      插桩输入
  expected.c   期望输出(规范化后逐行比对)
  sites.json   期望站点清单(可选;存在则比对)
"""

import dataclasses
import json
import pathlib

import pytest

from pa_debug.l1_transformer.rule import Blacklist
from pa_debug.l1_transformer.rules_loader import load_aliases, load_blacklist, load_rules
from pa_debug.l1_transformer.transformer import instrument

pytestmark = pytest.mark.integration

FIX = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "instrument"
ROOT = pathlib.Path(__file__).resolve().parents[2]
STUBS = ROOT / "stubs"
RULES = load_rules(ROOT / "rules")
ALIASES = load_aliases(ROOT / "rules")
BLACKLIST = load_blacklist(ROOT / "rules")
CASES = sorted(p.name for p in FIX.iterdir() if (p / "input.c").exists())


def _norm(text: str) -> list[str]:
    return [ln.rstrip() for ln in text.strip().splitlines()]


@pytest.mark.parametrize("case", CASES)
def test_instrumented_source_matches_expected(case, tmp_path):
    src = tmp_path / "input.c"
    src.write_text((FIX / case / "input.c").read_text())
    out_c, _ = instrument(
        str(src), rules=RULES, clang_args=["-I", str(STUBS)], aliases=ALIASES, blacklist=BLACKLIST
    )
    assert _norm(out_c) == _norm((FIX / case / "expected.c").read_text())


@pytest.mark.parametrize("case", CASES)
def test_manifest_matches_sites_json(case, tmp_path):
    src = tmp_path / "input.c"
    src.write_text((FIX / case / "input.c").read_text())
    _, manifest = instrument(
        str(src), rules=RULES, clang_args=["-I", str(STUBS)], aliases=ALIASES, blacklist=BLACKLIST
    )
    got = [dataclasses.asdict(s) for s in manifest]
    assert got == json.loads((FIX / case / "sites.json").read_text())


def test_blacklisted_file_is_left_unchanged(tmp_path):
    src = tmp_path / "input.c"
    text = (FIX / "single_conv" / "input.c").read_text()
    src.write_text(text)
    out_c, manifest = instrument(
        str(src),
        rules=RULES,
        clang_args=["-I", str(STUBS)],
        blacklist=Blacklist(skip_files=["input.c"]),
    )
    assert out_c == text
    assert manifest == []


def test_blacklisted_function_skips_only_its_macros(tmp_path):
    # multi_site: 函数 a()(line 4)与 b()(line 8)各一个 CONV;跳过 b 只剩 a。
    src = tmp_path / "input.c"
    src.write_text((FIX / "multi_site" / "input.c").read_text())
    _, manifest = instrument(
        str(src),
        rules=RULES,
        clang_args=["-I", str(STUBS)],
        blacklist=Blacklist(skip_functions=["b"]),
    )
    assert [s.site_id for s in manifest] == ["CONV@input.c:4"]
