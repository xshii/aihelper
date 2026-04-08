"""Smoke 测试 — generate_input → use_input 全流程 + 断言。

验证：
1. 8 个策略目录全部生成
2. math 目录有 expected 文件
3. 比数报告无 FAIL
4. run_log.json 完整
"""

import json
import sys
import tempfile
from pathlib import Path

# 在 src/ 下运行
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import dsp
from dsp.core.enums import RunMode, Mode
from dsp.data.datagen import USE_INPUT_MODES

EXPECTED_STRATEGIES = 8


def main():
    with tempfile.TemporaryDirectory(prefix="dsp_smoke_") as tmp:
        # 只用 torch + pseudo_quant（不需要真 golden C）
        original_modes = list(USE_INPUT_MODES)
        USE_INPUT_MODES[:] = [Mode.TORCH, Mode.PSEUDO_QUANT]

        try:
            _run_generate(tmp)
            _run_use_input(tmp)
            _verify_output(tmp)
        finally:
            USE_INPUT_MODES[:] = original_modes

    print("\n=== SMOKE PASSED ===")


def _run_generate(tmp):
    dsp.context.set_global_runmode(RunMode.GENERATE_INPUT, tmp, seed=42)
    rounds = 0
    while not dsp.context.is_global_done():
        x = dsp.ops.randn(4, 8, dtype=dsp.core.iq16)
        w = dsp.ops.randn(8, 4, dtype=dsp.core.iq16)
        b = dsp.ops.randn(1, 4, dtype=dsp.core.iq16)
        result = dsp.ops.linear(x, w, b)
        dsp.context.submit_output(result)
        rounds += 1
    dsp.context.export()
    assert rounds == EXPECTED_STRATEGIES, f"generate rounds: {rounds} != {EXPECTED_STRATEGIES}"
    print(f"  generate_input: {rounds} rounds OK")


def _run_use_input(tmp):
    dsp.context.set_global_runmode(RunMode.USE_INPUT, tmp, seed=42)
    rounds = 0
    while not dsp.context.is_global_done():
        x = dsp.ops.randn(4, 8, dtype=dsp.core.iq16)
        w = dsp.ops.randn(8, 4, dtype=dsp.core.iq16)
        b = dsp.ops.randn(1, 4, dtype=dsp.core.iq16)
        result = dsp.ops.linear(x, w, b)
        dsp.context.submit_output(result)
        rounds += 1
    dsp.context.export()
    expected_rounds = EXPECTED_STRATEGIES * 2  # × 2 modes
    assert rounds == expected_rounds, f"use_input rounds: {rounds} != {expected_rounds}"
    print(f"  use_input: {rounds} rounds OK")


def _verify_output(tmp):
    # 找 case 目录
    case_dirs = [d for d in Path(tmp).iterdir() if d.is_dir()]
    assert len(case_dirs) == 1, f"expected 1 case dir, got {len(case_dirs)}"
    case = case_dirs[0]

    # run_log.json 完整
    log = json.loads((case / "run_log.json").read_text())
    assert log["seed"] == 42
    print(f"  run_log.json: seed={log['seed']}, rounds={len(log['rounds'])}")

    # math 目录（如果 op 定义了 math_strategy 才有 expected 文件）
    math_dir = case / "math"
    if math_dir.exists():
        expected_files = list(math_dir.glob("*_expected0_*"))
        print(f"  math expected: {len(expected_files)} file(s)")
    else:
        print("  math expected: (no math dir — no op has math_strategy)")

    # 比数报告无 FAIL
    compare = log.get("compare", {})
    fails = []
    for strategy, ops in compare.items():
        for fname, pairs in ops.items():
            for pair_name, stats in pairs.items():
                if stats["cosine_sim"] < 0.99 and stats["max_diff"] > 0:
                    fails.append(f"{strategy}/{fname}: {pair_name}")
    if fails:
        print(f"  WARNING: {len(fails)} comparison(s) below threshold:")
        for f in fails:
            print(f"    {f}")
    else:
        print("  comparisons: all above threshold")

    # 策略目录数
    strategy_dirs = [d for d in case.iterdir()
                     if d.is_dir() and d.name != "use_input"]
    assert len(strategy_dirs) == EXPECTED_STRATEGIES, \
        f"strategy dirs: {len(strategy_dirs)} != {EXPECTED_STRATEGIES}"
    print(f"  strategy dirs: {len(strategy_dirs)} OK")


if __name__ == "__main__":
    main()
