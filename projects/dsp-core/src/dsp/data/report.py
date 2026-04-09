"""比数报告 — 跨模式输出对比。

从 use_input 产出的目录结构中加载各模式输出，两两比对，生成报告。
"""

from __future__ import annotations

import logging
from pathlib import Path

from .compare import compute_diff
from .pipe import DataPipe

logger = logging.getLogger("dsp.data")


def compare_all_modes(data_path: str, saved_dirs: list[str],
                      modes_list: list[str]) -> dict:
    """对比 use_input 产出的所有模式输出。

    Args:
        data_path: 用例根目录
        saved_dirs: 策略目录名列表
        modes_list: 模式列表

    Returns:
        {strategy: {output_file: {"mode_a vs mode_b": diff_stats}}}
    """
    from ..core.enums import RunMode
    base = Path(data_path) / RunMode.USE_INPUT
    gen_base = Path(data_path)
    report = {}
    for strategy_name in saved_dirs:
        strategy_report = _compare_strategy(
            base / strategy_name, modes_list,
            gen_dir=gen_base / strategy_name,  # generate_input 的 torch 输出作为基准
        )
        # math 策略：额外对比 expected vs torch actual
        expected_report = _compare_expected(
            gen_dir=gen_base / strategy_name,
            use_dir=base / strategy_name,
            modes_list=["torch"] + modes_list,  # torch 从 gen_dir 取
        )
        if expected_report:
            strategy_report.update(expected_report)
        if strategy_report:
            report[strategy_name] = strategy_report
    return report


def print_compare_summary(report: dict):
    """打印比数摘要到终端。阈值从 config.compare 读。"""
    from ..config import config as cfg
    pass_cos = cfg.compare.pass_cosine
    warn_cos = cfg.compare.warn_cosine

    print("\n" + "=" * 60)
    print("比数报告")
    print("=" * 60)
    for strategy, ops in report.items():
        print(f"\n[{strategy}]")
        for op_file, pairs in ops.items():
            for pair_name, stats in pairs.items():
                max_d = stats["max_diff"]
                cos_s = stats["cosine_sim"]
                if max_d == 0:
                    status = "PASS"
                elif cos_s > pass_cos:
                    status = "PASS"
                elif cos_s > warn_cos:
                    status = "WARN"
                else:
                        status = "FAIL"
                print(
                    f"  {op_file}: {pair_name}  "
                    f"max_diff={max_d:.2e}  cosine={cos_s:.6f}  [{status}]"
                )
    print("=" * 60)


def _compare_expected(gen_dir: Path, use_dir: Path, modes_list: list[str]) -> dict:
    """对比 math strategy 的 expected 文件 vs 各模式 actual 输出。"""
    if not gen_dir.exists():
        return {}
    expected_files = list(gen_dir.glob("*_expected0_*"))
    if not expected_files:
        return {}

    result = {}
    for exp_path in expected_files:
        try:
            exp_tensor = DataPipe.load(str(exp_path)).tensor
        except Exception as e:
            logger.warning("加载 expected 失败 %s: %s", exp_path, e)
            continue

        # 从 expected 文件名推导对应的 output 文件名
        out_fname = exp_path.name.replace("_expected0_", "_output0_")
        pairs = {}
        for m in modes_list:
            # torch 输出在 gen_dir，其他在 use_dir/{mode}/
            if m == "torch":
                out_path = gen_dir / out_fname
            else:
                out_path = use_dir / m / out_fname
            if not out_path.exists():
                continue
            try:
                actual = DataPipe.load(str(out_path)).tensor
                pairs[f"expected vs {m}"] = compute_diff(exp_tensor, actual)
            except Exception as e:
                logger.warning("对比 expected vs %s 失败: %s", m, e)
        if pairs:
            result[exp_path.name] = pairs
    return result


def _compare_strategy(strategy_dir: Path, modes_list: list[str],
                      gen_dir: Path = None) -> dict:
    """对比各模式输出。gen_dir 是 generate_input 的 torch 输出目录（作为基准）。"""
    if not strategy_dir.exists():
        return {}

    # use_input 的各模式目录
    mode_dirs = {m: strategy_dir / m for m in modes_list
                 if (strategy_dir / m).exists()}

    # 加入 generate_input 的 torch 输出作为基准
    if gen_dir is not None and gen_dir.exists():
        mode_dirs["torch"] = gen_dir

    if len(mode_dirs) < 2:
        return {}

    # 从任一模式目录取 output 文件列表
    ref_dir = next(iter(mode_dirs.values()))
    output_files = [f.name for f in ref_dir.glob("*_output*_*.txt")]

    result = {}
    for fname in output_files:
        pairs = _compare_file_across_modes(fname, mode_dirs)
        if pairs:
            result[fname] = pairs
    return result


def _compare_file_across_modes(fname: str, mode_dirs: dict) -> dict:
    mode_tensors = {}
    for m, d in mode_dirs.items():
        fpath = d / fname
        if fpath.exists():
            try:
                mode_tensors[m] = DataPipe.load(str(fpath)).tensor
            except Exception as e:
                logger.warning("加载失败 %s: %s", fpath, e)

    if len(mode_tensors) < 2:
        return {}

    pairs = {}
    modes = list(mode_tensors.keys())
    for i, ma in enumerate(modes):
        for mb in modes[i + 1:]:
            try:
                pairs[f"{ma} vs {mb}"] = compute_diff(mode_tensors[ma], mode_tensors[mb])
            except Exception as e:
                logger.warning("比较失败 %s vs %s: %s", ma, mb, e)
    return pairs
