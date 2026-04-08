"""验证循环状态机 — generate_input / use_input。

只管状态推进和轮次控制。
数据 I/O 由 data 模块通过 hook 完成。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import torch

from ..core.tensor import DSPTensor
from ..core.dtype import DSPDtype
from ..core.enums import Mode, Format, RunMode
from .mode import set_mode as _set_compute_mode
from .case import make_case_dir, resolve_case_dir_and_seed
from ..data.datagen import (
    DataStrategy, DEFAULT_STRATEGIES, USE_INPUT_MODES,
    generate_by_strategy,
)
from ..data.io import (
    tensor_to_uint32_lines, make_filename, parse_filename,
)
from ..data.layout import infer_format

logger = logging.getLogger("dsp.context")


# ============================================================
# RunState
# ============================================================

@dataclass
class RunState:
    active: bool = False
    runmode: str = ""
    data_path: str = ""
    seed: int = 0

    round_index: int = 0
    total_rounds: int = 0
    done: bool = False

    strategies: list[DataStrategy] = field(default_factory=list)
    strategy_index: int = 0
    current_strategy: Optional[DataStrategy] = None

    saved_dirs: list[str] = field(default_factory=list)
    modes_list: list[str] = field(default_factory=list)
    mode_index: int = 0
    current_mode: str = Mode.TORCH

    randn_counter: int = 0
    op_id_counter: int = 0
    current_op_name: str = ""

    results: list[dict] = field(default_factory=list)
    round_logs: list[str] = field(default_factory=list)


_state = RunState()


# ============================================================
# 公开 API
# ============================================================

def set_global_runmode(runmode: str, data_path: str = None, seed: int = None):
    """设置全局 runmode。data_path 默认从 config.yaml 的 output.root 取。"""
    if data_path is None:
        from ..config import config as _cfg
        data_path = _cfg.output.root
    if seed is None:
        from ..config import config as _cfg
        seed = _cfg.output.seed

    if runmode == RunMode.GENERATE_INPUT:
        data_path = make_case_dir(data_path, seed)
        logger.info("用例目录: %s (seed=%d)", data_path, seed)
    elif runmode == RunMode.USE_INPUT:
        data_path, seed = resolve_case_dir_and_seed(data_path, seed)
        logger.info("加载目录: %s (seed=%d)", data_path, seed)

    torch.manual_seed(seed)

    global _state
    _state = RunState(active=True, runmode=runmode, data_path=data_path, seed=seed)

    _SETUP = {
        RunMode.GENERATE_INPUT: _setup_generate_input,
        RunMode.USE_INPUT: _setup_use_input,
    }
    setup_fn = _SETUP.get(runmode)
    if setup_fn is None:
        raise ValueError(f"未知 runmode: '{runmode}'。可用: {list(_SETUP)}")
    setup_fn()


def is_global_done() -> bool:
    return _state.done


def is_runmode_active() -> bool:
    return _state.active


def submit_output(result):
    """记录本轮结果，推进到下一轮。"""
    if not _state.active:
        return

    _state.round_logs.append(
        f"round {_state.round_index}: "
        f"strategy={_state.current_strategy}, mode={_state.current_mode}"
    )
    _state.results.append({
        "round": _state.round_index,
        "strategy": str(_state.current_strategy),
        "mode": _state.current_mode,
        "shape": list(result.shape) if hasattr(result, "shape") else None,
    })
    logger.info(
        "[round %d/%d] strategy=%s, mode=%s",
        _state.round_index + 1, _state.total_rounds,
        _state.current_strategy, _state.current_mode,
    )
    _advance_round()


def export():
    """导出日志 + 比数报告。"""
    if not _state.data_path:
        return

    out_dir = Path(_state.data_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    compare_report = {}
    if _state.runmode == RunMode.USE_INPUT and _state.saved_dirs:
        compare_report = _compare_all_modes()

    log_data = {
        "runmode": _state.runmode,
        "seed": _state.seed,
        "rounds": _state.results,
    }
    if compare_report:
        log_data["compare"] = compare_report
    (out_dir / "run_log.json").write_text(
        json.dumps(log_data, indent=2, ensure_ascii=False)
    )

    lines = [
        f"runmode: {_state.runmode}",
        f"seed: {_state.seed}",
        f"rounds: {len(_state.results)}",
        "",
    ]
    lines.extend(_state.round_logs)
    if compare_report:
        lines.append("")
        lines.append("=" * 60)
        lines.append("比数报告")
        lines.append("=" * 60)
        for strategy, ops in compare_report.items():
            lines.append(f"\n[{strategy}]")
            for op_file, pairs in ops.items():
                for pair_name, stats in pairs.items():
                    lines.append(
                        f"  {op_file}: {pair_name}  "
                        f"max_diff={stats['max_diff']:.2e}  "
                        f"mean_diff={stats['mean_diff']:.2e}  "
                        f"cosine_sim={stats['cosine_sim']:.6f}"
                    )
    (out_dir / "run_log.txt").write_text("\n".join(lines) + "\n")
    logger.info("导出日志: %s", out_dir)

    if compare_report:
        _print_compare_summary(compare_report)
        _export_html(compare_report)


# ============================================================
# Setup
# ============================================================

def _setup_generate_input():
    _state.strategies = list(DEFAULT_STRATEGIES)
    _state.total_rounds = len(_state.strategies)
    _state.strategy_index = 0
    _state.current_strategy = _state.strategies[0]
    _state.current_mode = Mode.TORCH
    _set_compute_mode(Mode.TORCH)
    _prepare_dir(_current_round_dir())
    logger.info("generate_input: %d 种策略", _state.total_rounds)


def _setup_use_input():
    _state.saved_dirs = _scan_saved_dirs()
    _state.modes_list = list(USE_INPUT_MODES)
    _state.mode_index = 0
    _state.strategy_index = 0
    _state.total_rounds = len(_state.saved_dirs) * len(_state.modes_list)

    if _state.total_rounds == 0:
        _state.done = True
        logger.warning("use_input: 未找到已保存的数据目录")
        return

    _state.current_mode = _state.modes_list[0]
    _state.current_strategy = DataStrategy(_state.saved_dirs[0])
    _set_compute_mode(_state.current_mode)
    _prepare_dir(_current_round_dir())
    logger.info(
        "use_input: %d 目录 × %d 模式 = %d 轮",
        len(_state.saved_dirs), len(_state.modes_list), _state.total_rounds,
    )


def _scan_saved_dirs() -> list[str]:
    base = Path(_state.data_path)
    if not base.exists():
        return []
    dirs = []
    for d in sorted(base.iterdir()):
        if d.is_dir() and d.name != RunMode.USE_INPUT and not d.name.startswith("."):
            if any(d.glob("*.txt")):
                dirs.append(d.name)
    return dirs


# ============================================================
# 轮次推进
# ============================================================

def _advance_round():
    {RunMode.GENERATE_INPUT: _advance_generate, RunMode.USE_INPUT: _advance_use_input}[
        _state.runmode
    ]()


def _advance_generate():
    _state.strategy_index += 1
    _state.round_index += 1
    _state.randn_counter = 0
    _state.op_id_counter = 0

    if _state.strategy_index >= len(_state.strategies):
        _state.done = True
        logger.info("generate_input 完成: %d 轮", _state.round_index)
        return

    _state.current_strategy = _state.strategies[_state.strategy_index]
    torch.manual_seed(_state.seed + _state.strategy_index)
    _prepare_dir(_current_round_dir())


def _advance_use_input():
    _state.mode_index += 1
    _state.round_index += 1
    _state.randn_counter = 0
    _state.op_id_counter = 0

    if _state.mode_index >= len(_state.modes_list):
        _state.mode_index = 0
        _state.strategy_index += 1

        if _state.strategy_index >= len(_state.saved_dirs):
            _state.done = True
            _set_compute_mode(Mode.TORCH)
            logger.info("use_input 完成: %d 轮", _state.round_index)
            return

    _state.current_mode = _state.modes_list[_state.mode_index]
    _state.current_strategy = DataStrategy(_state.saved_dirs[_state.strategy_index])
    _set_compute_mode(_state.current_mode)
    _prepare_dir(_current_round_dir())


# ============================================================
# 目录
# ============================================================

def _current_round_dir() -> str:
    if _state.runmode == RunMode.GENERATE_INPUT:
        return str(Path(_state.data_path) / _state.current_strategy.name)
    strategy_name = _state.saved_dirs[_state.strategy_index]
    return str(
        Path(_state.data_path) / RunMode.USE_INPUT / strategy_name / _state.current_mode
    )


def _prepare_dir(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)


# ============================================================
# 数据拦截（由 ops 调用）
# ============================================================

def get_current_strategy():
    """返回当前 DataStrategy（供 ops wrapper 查询）。无活跃策略时返回 None。"""
    if _state.active and _state.current_strategy is not None:
        return _state.current_strategy
    return None


def intercepted_randn(*size, dtype: DSPDtype) -> DSPTensor:
    counter = _state.randn_counter
    _state.randn_counter += 1

    if _state.runmode == RunMode.GENERATE_INPUT:
        strategy = _state.current_strategy
        if strategy is not None and strategy.name == "math":  # 同 ops.MATH_STRATEGY_NAME
            # math 策略：生成随机数据，打标 randn，由 op-level 拦截替换
            t = torch.randn(*size, dtype=dtype.torch_dtype)
            result = DSPTensor.create(t, dtype)
            result._source = "randn"
            return result
        t = generate_by_strategy(
            *size, dtype_torch=dtype.torch_dtype, strategy=strategy,
        )
        result = DSPTensor.create(t, dtype)
        result._source = "randn"
        return result

    if _state.runmode == RunMode.USE_INPUT:
        return _load_randn_input(counter, size, dtype)

    result = DSPTensor.create(torch.randn(*size, dtype=dtype.torch_dtype), dtype)
    result._source = "randn"
    return result


def _load_randn_input(counter, size, dtype):
    from ..data.pipe import DataPipe

    strategy_name = _state.saved_dirs[_state.strategy_index]
    src_dir = Path(_state.data_path) / strategy_name

    matches = list(src_dir.glob(f"*_input{counter}_*"))
    if matches:
        pipe = DataPipe.load(str(matches[0]))
        return DSPTensor.create(pipe.tensor, dtype)

    logger.warning("未找到 input%d 文件 (dir=%s)，降级为随机", counter, src_dir)
    return DSPTensor.create(torch.randn(*size, dtype=dtype.torch_dtype), dtype)


# ============================================================
# 算子数据保存（由 ops hook 调用）
# ============================================================

def save_op_inputs(op_name, param_names, args, format_hints):
    from ..data.pipe import DataPipe

    _state.current_op_name = op_name
    op_id = _state.op_id_counter
    out_dir = _current_round_dir()

    for i, arg in enumerate(args):
        if not isinstance(arg, torch.Tensor):
            continue
        name = param_names[i] if i < len(param_names) else f"input{i}"
        operand = f"input{i}"

        dtype_name = "float32"
        if isinstance(arg, DSPTensor) and arg._dsp_dtype is not None:
            dtype_name = arg._dsp_dtype.name

        fmt = format_hints.get(name, infer_format(arg))

        filename = make_filename(op_name, op_id, operand, dtype_name, tuple(arg.shape), fmt)
        DataPipe(arg, dtype=dtype_name).layout(fmt).export(
            str(Path(out_dir) / filename)
        )

    _write_input_order(out_dir, op_name, op_id, param_names, args)


def save_op_output(op_name, result):
    from ..data.pipe import DataPipe

    op_id = _state.op_id_counter
    _state.op_id_counter += 1

    if not isinstance(result, torch.Tensor):
        return

    out_dir = _current_round_dir()
    dtype_name = "float32"
    if isinstance(result, DSPTensor) and result._dsp_dtype is not None:
        dtype_name = result._dsp_dtype.name

    fmt = infer_format(result)
    filename = make_filename(op_name, op_id, "output0", dtype_name, tuple(result.shape), fmt)
    DataPipe(result, dtype=dtype_name).layout(fmt).export(
        str(Path(out_dir) / filename)
    )


def clear_current_op():
    _state.current_op_name = ""


def _write_input_order(out_dir, op_name, op_id, param_names, args):
    path = Path(out_dir) / f"{op_name}_{op_id}_input_order.txt"
    lines = []
    for i, arg in enumerate(args):
        if not isinstance(arg, torch.Tensor):
            continue
        name = param_names[i] if i < len(param_names) else f"input{i}"
        lines.append(f"input{i}: {name}")
    path.write_text("\n".join(lines) + "\n")


# ============================================================
# 比数（委托给 data/report.py）
# ============================================================

def _compare_all_modes():
    from ..data.report import compare_all_modes
    return compare_all_modes(_state.data_path, _state.saved_dirs, _state.modes_list)


def _export_html(compare_report):
    from ..data.html_report import export_html
    export_html(_state.data_path, compare_report, _state.modes_list)


def _print_compare_summary(report):
    from ..data.report import print_compare_summary
    print_compare_summary(report)
    print("=" * 60)
