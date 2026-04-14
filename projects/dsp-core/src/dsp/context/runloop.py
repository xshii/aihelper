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
from ..core.enums import Mode, Format, RunMode, TensorSource
from .mode import set_mode as _set_compute_mode
from .case import make_case_dir, resolve_case_dir_and_seed
from ..data.datagen import (
    DataStrategy, DEFAULT_STRATEGIES, USE_INPUT_MODES,
    generate_by_strategy,
)
from ..data.io import (
    make_filename,
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

    # USE_INPUT_DUT: 外部 DUT 输入源目录（平铺的 *_zz.txt / *_nn.txt / *_nd.txt 文件）
    dut_source: str = ""

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

    op_id_counter: int = 0

    results: list[dict] = field(default_factory=list)
    round_logs: list[str] = field(default_factory=list)


_state = RunState()


# ============================================================
# 公开 API
# ============================================================

def set_global_runmode(runmode: str, data_path: str = None, seed: int = None,
                       dut_source: str = None):
    """设置全局 runmode。data_path 默认从 config.yaml 的 output.root 取。

    Args:
        dut_source: USE_INPUT_DUT 专用 —— 外部 DUT 输入源目录（平铺文件，
                    无 strategy 子目录）。若 None，则尝试在 data_path 下找 dut/ 子目录。
    """
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
    elif runmode == RunMode.USE_INPUT_DUT:
        data_path = make_case_dir(data_path, seed)
        logger.info("use_input_dut 用例目录: %s (seed=%d, dut_source=%s)",
                    data_path, seed, dut_source)

    torch.manual_seed(seed)

    global _state
    _state = RunState(
        active=True, runmode=runmode, data_path=data_path, seed=seed,
        dut_source=dut_source or "",
    )

    # GENERATE_INPUT 单独一路；USE_INPUT / USE_INPUT_DUT 共用 _setup_use_input
    if runmode == RunMode.GENERATE_INPUT:
        _setup_generate_input()
    elif runmode in (RunMode.USE_INPUT, RunMode.USE_INPUT_DUT):
        _setup_use_input()
    else:
        raise ValueError(f"未知 runmode: '{runmode}'")


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
    elif _state.runmode == RunMode.USE_INPUT_DUT and _state.dut_source:
        compare_report = _compare_use_input_dut()

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
    """USE_INPUT / USE_INPUT_DUT 共用: saved_dirs × modes_list 两层循环。

    - USE_INPUT:     saved_dirs 扫 data_path 下的 strategy 子目录
    - USE_INPUT_DUT: saved_dirs 记作 ["dut"]（单占位），输入源在 dut_source 平铺目录
                     modes_list 默认沿用 USE_INPUT_MODES 并自动补 Mode.TORCH
                     （USE_INPUT_DUT 没有单独的 torch 参考轮，需要 torch 做无损基线）
    """
    if _state.runmode == RunMode.USE_INPUT_DUT:
        if not _state.dut_source or not Path(_state.dut_source).exists():
            _state.done = True
            logger.error("use_input_dut: dut_source 不存在: %s", _state.dut_source)
            return
        _state.saved_dirs = ["dut"]
        _state.modes_list = list(USE_INPUT_MODES)
        if Mode.TORCH not in _state.modes_list:
            _state.modes_list.insert(0, Mode.TORCH)
    else:
        _state.saved_dirs = _scan_saved_dirs()
        _state.modes_list = list(USE_INPUT_MODES)

    _state.mode_index = 0
    _state.strategy_index = 0
    _state.total_rounds = len(_state.saved_dirs) * len(_state.modes_list)

    if _state.total_rounds == 0:
        _state.done = True
        logger.warning("%s: 未找到已保存的数据", _state.runmode)
        return

    _state.current_mode = _state.modes_list[0]
    _state.current_strategy = DataStrategy(_state.saved_dirs[0])
    _set_compute_mode(_state.current_mode)
    _prepare_dir(_current_round_dir())
    logger.info(
        "%s: %d 目录 × %d 模式 = %d 轮",
        _state.runmode,
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
    # USE_INPUT 和 USE_INPUT_DUT 共用 _advance_use_input
    if _state.runmode == RunMode.GENERATE_INPUT:
        _advance_generate()
    else:
        _advance_use_input()


def _advance_generate():
    _state.strategy_index += 1
    _state.round_index += 1
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
    base = Path(_state.data_path) / _state.runmode
    # USE_INPUT_DUT: 无真 strategy，扁平化为 use_input_dut/<mode>/
    if _state.runmode == RunMode.USE_INPUT_DUT:
        return str(base / _state.current_mode)
    # USE_INPUT: use_input/<strategy>/<mode>/
    strategy_name = _state.saved_dirs[_state.strategy_index]
    return str(base / strategy_name / _state.current_mode)


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
    """拦截 randn。

    GENERATE_INPUT: 按 strategy 生成数据
    USE_INPUT: passthrough — 不替换，op 级别会从磁盘加载保存的输入
    其他: 普通 randn

    内存全程 double 存储；dtype 只是标签，pre_quantize 会按需把量化误差打进去。
    """
    if _state.runmode == RunMode.GENERATE_INPUT:
        strategy = _state.current_strategy
        if strategy is not None and strategy.name == "math":
            t = torch.randn(*size, dtype=torch.double)
        else:
            t = generate_by_strategy(*size, dtype_torch=torch.double, strategy=strategy)
    else:
        # USE_INPUT 和其他模式：普通 randn（值在 USE_INPUT 下会被 op 层覆盖）
        t = torch.randn(*size, dtype=torch.double)

    result = DSPTensor.create(t, dtype)
    result._source = TensorSource.RANDN
    return result


def get_current_runmode():
    return _state.runmode


def load_op_inputs(op_name: str, n_inputs: int) -> list:
    """从磁盘加载当前 op 的输入。USE_INPUT / USE_INPUT_DUT 模式用。

    使用 _state.op_id_counter 作为当前 op_id（和 save 同步）。
    """
    from ..data.pipe import DataPipe

    op_id = _state.op_id_counter

    if _state.runmode == RunMode.USE_INPUT_DUT:
        # 从 dut_source 平铺目录读 bf16/bf8 bits，经 codec 还原成 double tensor
        src_dir = Path(_state.dut_source)
        loaded = []
        for i in range(n_inputs):
            pattern = f"{op_name}_{op_id}_input{i}_*.txt"
            matches = list(src_dir.glob(pattern))
            if not matches:
                raise FileNotFoundError(
                    f"未找到 DUT 输入 {op_name}_{op_id}_input{i} (dir={src_dir})"
                )
            loaded.append(_load_dut_file(matches[0]))
        return loaded

    # USE_INPUT: 从 ND 文件（double）加载
    strategy_name = _state.saved_dirs[_state.strategy_index]
    src_dir = Path(_state.data_path) / strategy_name

    loaded = []
    for i in range(n_inputs):
        # DUT 文件在 dut/ 子目录，这里只扫根目录
        pattern = f"{op_name}_{op_id}_input{i}_*.txt"
        matches = list(src_dir.glob(pattern))
        if not matches:
            raise FileNotFoundError(
                f"未找到 {op_name}_{op_id}_input{i} 文件 (dir={src_dir})"
            )
        pipe = DataPipe.load(str(matches[0]))
        loaded.append(pipe.tensor)
    return loaded


# ============================================================
# 算子数据保存（由 ops hook 调用）
# ============================================================

def _get_dtype_name(t: torch.Tensor) -> str:
    """按 tensor 真实 torch dtype 命名（用于 ND 文件）。未注册的 torch dtype 回退到原始名字。"""
    from ..core.dtype import dtype_from_torch
    d = dtype_from_torch(t.dtype)
    return d.name if d else str(t.dtype).replace("torch.", "")


def _to_dut_bits(t: torch.Tensor, dsp_dtype, fmt) -> torch.Tensor:
    """double tensor → padded + block 重排 + cast 到硬件原生 torch dtype。

    结果 tensor 的 bit 模式就是硬件 DUT 文件应写的内容（bf16/bf8 等）。
    """
    from ..core.block import pad_to_block, to_block
    fmt = Format(fmt) if not isinstance(fmt, Format) else fmt
    name = dsp_dtype.name
    if t.ndim >= 2 and fmt != Format.ND:
        padded = pad_to_block(t, name, fmt)
        blocked = to_block(padded, name, fmt)
    else:
        blocked = t
    # 值在此之前已经是 bf16 量化过的 double（经 pre_quantize / golden_c 输出），
    # .to(bf16) 是无损截断。
    return blocked.to(dsp_dtype.torch_dtype)


def _load_dut_file(path: Path) -> torch.Tensor:
    """从 DUT 文件加载 → double tensor (原始 shape, 无 padding)。

    DUT 文件存储硬件原生 bit 模式（bf16/bf8 ...），padded 且按 block 重排。
    本函数负责：读 bytes → view 为原生 torch dtype → .double() → 反 block → 裁 padding。
    """
    from ..core.block import get_block_shape, pad_dim, from_block
    from ..core.dtype import get_dtype
    from ..data.io import parse_filename, uint32_lines_to_bytes
    import numpy as np

    meta = parse_filename(str(path))
    dtype_name = meta.get("dtype", "bf16")
    orig_shape = meta.get("shape", ())
    fmt = Format(meta.get("format", Format.ND))

    dsp_dtype = get_dtype(dtype_name)
    torch_dtype = dsp_dtype.torch_dtype

    # 计算 padded shape（DUT 文件里含 padding）
    if len(orig_shape) >= 2 and fmt != Format.ND:
        bh, bw = get_block_shape(dtype_name, fmt)
        padded_last2 = (pad_dim(orig_shape[-2], bh), pad_dim(orig_shape[-1], bw))
        padded_shape = (*orig_shape[:-2], *padded_last2)
    else:
        padded_shape = orig_shape

    # 读取原始字节
    with open(path) as f:
        lines = f.readlines()
    raw = uint32_lines_to_bytes(lines)

    # numpy 不支持 bf16/fp8 → 用等宽 int 类型 view 回硬件 dtype
    if torch_dtype == torch.bfloat16:
        view_dtype = torch.int16
    elif torch_dtype == torch.float8_e4m3fn:
        view_dtype = torch.int8
    else:
        view_dtype = torch_dtype

    np_dtype = torch.zeros(1, dtype=view_dtype).numpy().dtype
    total = int(np.prod(padded_shape)) if padded_shape else len(raw) // np_dtype.itemsize
    arr = np.frombuffer(raw, dtype=np_dtype, count=total).copy()
    tensor = torch.from_numpy(arr)
    if view_dtype != torch_dtype:
        tensor = tensor.view(torch_dtype)

    # 硬件原生 → double（现在所有内存都是 double）
    double_blocked = tensor.double()

    # 反 block: blocked → nd + 去 padding
    if len(orig_shape) >= 2 and fmt != Format.ND:
        return from_block(double_blocked, dtype_name, fmt, tuple(orig_shape))
    return double_blocked.reshape(orig_shape)


def _save_tensor(tensor: torch.Tensor, op_name: str, op_id: int,
                 operand: str, fmt_hint: Optional[Format] = None) -> None:
    """写一份 ND（按真实 torch dtype） + 可选的 DUT（硬件原生 bits，写 dut/ 子目录）。"""
    from ..data.pipe import DataPipe

    t_cpu = tensor.detach().cpu()
    out_dir = Path(_current_round_dir())
    storage_name = _get_dtype_name(t_cpu)

    # ND 文件
    nd_name = make_filename(op_name, op_id, operand, storage_name, tuple(t_cpu.shape), Format.ND)
    DataPipe(t_cpu, dtype=storage_name).export(str(out_dir / nd_name))

    # golden_c 额外: DUT 文件（硬件原生 bits），写到 dut/ 子目录
    # 只对带 DSPDtype 的 tensor 写 DUT；double tensor 没有硬件原生表示
    dsp_dtype = tensor._dsp_dtype if isinstance(tensor, DSPTensor) else None
    if _state.current_mode == Mode.GOLDEN_C and dsp_dtype is not None and dsp_dtype.name != "double":
        dut_dir = out_dir / "dut"
        dut_dir.mkdir(parents=True, exist_ok=True)
        dut_fmt = fmt_hint if fmt_hint is not None else infer_format(t_cpu)
        dut_bits = _to_dut_bits(t_cpu, dsp_dtype, dut_fmt)
        dut_name = make_filename(op_name, op_id, operand, dsp_dtype.name, tuple(t_cpu.shape), dut_fmt)
        DataPipe(dut_bits, dtype=dsp_dtype.name, fmt=dut_fmt).export(str(dut_dir / dut_name))


def save_op_inputs(op_name, param_names, args, format_hints):
    """保存算子每个 tensor 输入。ND 按真实 dtype，golden_c 额外导出 DUT。"""
    op_id = _state.op_id_counter
    out_dir = _current_round_dir()

    for i, arg in enumerate(args):
        if not isinstance(arg, torch.Tensor):
            continue
        name = param_names[i] if i < len(param_names) else f"input{i}"
        fmt_hint = format_hints.get(name) if _state.current_mode == Mode.GOLDEN_C else None
        _save_tensor(arg, op_name, op_id, f"input{i}", fmt_hint=fmt_hint)

    _write_input_order(out_dir, op_name, op_id, param_names, args)


def save_op_output(op_name, result):
    """保存算子输出。

    支持单 tensor 和 tuple/list of tensor。
    每个 output slot 的 fmt 优先从 ops._OP_OUTPUT_FMTS 取（显式声明）；
    未声明的 op 不传 fmt_hint，由 _save_tensor 走 infer_format 兜底（保留旧行为）。
    """
    op_id = _state.op_id_counter
    _state.op_id_counter += 1

    if isinstance(result, torch.Tensor):
        outputs = [result]
    elif isinstance(result, (tuple, list)):
        outputs = [t for t in result if isinstance(t, torch.Tensor)]
    else:
        return

    if not outputs:
        return

    from ..ops import _OP_OUTPUT_FMTS
    declared_fmts = _OP_OUTPUT_FMTS.get(op_name)   # None = 未显式声明

    for i, t in enumerate(outputs):
        if declared_fmts is not None and i < len(declared_fmts):
            fmt_hint = declared_fmts[i]
        else:
            fmt_hint = None   # 走 _save_tensor 内部的 infer_format
        _save_tensor(t, op_name, op_id, f"output{i}", fmt_hint=fmt_hint)


def save_op_expected(op_name, expected):
    """保存 math strategy 的期望输出。只写 ND（不进 dut/）。"""
    from ..data.pipe import DataPipe

    if not isinstance(expected, torch.Tensor):
        return

    op_id = _state.op_id_counter - 1  # save_op_output 已经 +1
    out_dir = _current_round_dir()
    t_cpu = expected.detach().cpu()
    storage_name = _get_dtype_name(t_cpu)
    filename = make_filename(op_name, op_id, "expected0", storage_name, tuple(t_cpu.shape), Format.ND)
    DataPipe(t_cpu, dtype=storage_name).export(str(Path(out_dir) / filename))
    logger.info("[math] %s: saved expected output → %s", op_name, filename)


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


def _compare_use_input_dut() -> dict:
    """USE_INPUT_DUT 比数：每个模式的 output vs dut_source 里的 expected DUT 文件。

    dut_source 里的 `<op>_<id>_output0_*.txt` 是外部硬件产出的期望，解码成 double 后
    和 data_path/use_input_dut/<mode>/ 下每个模式的 ND 输出做 compute_diff。
    """
    from ..data.compare import compute_diff
    from ..data.pipe import DataPipe
    from ..data.io import parse_filename

    src = Path(_state.dut_source)
    base = Path(_state.data_path) / _state.runmode

    report = {"dut": {}}
    for exp_path in sorted(src.glob("*_output0_*.txt")):
        try:
            exp_tensor = _load_dut_file(exp_path)
        except Exception as e:
            logger.warning("加载 expected %s 失败: %s", exp_path.name, e)
            continue

        meta = parse_filename(exp_path.name)
        op = meta.get("op")
        op_id = meta.get("op_id")
        operand = meta.get("operand")
        if not op or op_id is None or not operand:
            continue

        pairs = {}
        for mode in _state.modes_list:
            pattern = f"{op}_{op_id}_{operand}_*_nd.txt"
            matches = list((base / mode).glob(pattern))
            if not matches:
                continue
            act_tensor = DataPipe.load(str(matches[0])).tensor
            pairs[f"expected vs {mode}"] = compute_diff(act_tensor, exp_tensor)

        if pairs:
            report["dut"][exp_path.name] = pairs

    return report


def _export_html(compare_report):
    from ..data.viz import export_html
    export_html(_state.data_path, compare_report, _state.modes_list,
                runmode=_state.runmode)


def _print_compare_summary(report):
    from ..data.report import print_compare_summary
    print_compare_summary(report)
    print("=" * 60)
