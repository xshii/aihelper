"""上下文管理 — App 层，组合 data + ops。

子模块:
    mode      — 运行模式切换（torch / pseudo_quant / golden_c）
    runloop   — 验证循环状态机
    case      — 用例目录 + seed 管理

compute config:
    set_compute_config  — 设置全局默认计算精度和输出类型
    get_compute_config  — 查询当前配置
"""

from .mode import (
    set_mode, get_current_mode, mode_context,
    VALID_MODES,
    PseudoQuantMode, GoldenCMode,
    register_golden_aten,
)
from .runloop import (
    set_global_runmode, is_global_done, is_runmode_active,
    submit_output, export,
    save_op_inputs, save_op_output, save_op_expected, intercepted_randn,
    get_current_strategy, load_op_inputs, get_current_runmode,
)

# 注入 hooks 到 ops 和 data（解除反向依赖）
from ..ops import set_ops_hooks
set_ops_hooks(
    get_mode=get_current_mode,
    is_runmode_active=is_runmode_active,
    save_op_inputs=save_op_inputs,
    save_op_output=save_op_output,
    get_compute_config=lambda: get_compute_config(),
    get_current_strategy=get_current_strategy,
    save_op_expected=save_op_expected,
    load_op_inputs=load_op_inputs,
    get_runmode=get_current_runmode,
)

from ..data.factory import set_randn_interceptor
set_randn_interceptor(
    lambda *size, dtype: intercepted_randn(*size, dtype=dtype) if is_runmode_active() else None
)


# ============================================================
# Compute Config — 全局默认计算精度
# ============================================================

_compute_config = {
    "compute": None,       # 默认计算精度（None = 不过滤，取 manifest 第一个匹配）
    "output_dtype": None,  # 默认输出类型（None = 不过滤）
}


def set_compute_config(compute=None, output_dtype=None):
    """设置全局默认计算精度。golden_c 模式下生效。

    Args:
        compute: DType.DUT 或 DType.REAL 枚举值
        output_dtype: 输出类型名，如 "int16"

    用法:
        dsp.context.set_compute_config(compute=DType.DUT.INT16, output_dtype=DType.DUT.INT16)
    """
    _compute_config["compute"] = compute.value if hasattr(compute, 'value') else compute
    _compute_config["output_dtype"] = output_dtype.value if hasattr(output_dtype, 'value') else output_dtype


def get_compute_config() -> dict:
    """获取当前 compute config。"""
    return dict(_compute_config)


def run(
    main_fn,
    runmode=None,
    data_path=None,
    seed=None,
    compute=None,
    output_dtype=None,
    strategies=None,
    modes=None,
    dut_source=None,
):
    """一键运行验证循环。所有可配置项集中在这里。

    Args:                                         默认值（来自 config.py）
        main_fn:      用户计算函数，返回 tensor   （必填）
        runmode:      RunMode 枚举                sys.argv[1] → GENERATE_INPUT
        data_path:    输出根目录                   config.output.root = "{cwd}/output/"
        seed:         随机种子                     config.output.seed = 1
        compute:      计算精度 (DType.DUT/REAL)    config.compute.default_compute = None（不过滤）
        output_dtype: 输出类型 (DType.DUT/REAL)    config.compute.default_output_dtype = None（不过滤）
        strategies:   数据策略列表                  config.run.strategies = [
                                                     math, precision_exact, random,
                                                     sparse_30/50/90/9999, corner_all_zero
                                                   ]（共 8 种）
        modes:        use_input 模式列表           config.run.modes = [torch, pseudo_quant, golden_c]

    用法:
        dsp.context.run(main)                      # 零配置
        dsp.context.run(main, seed=42)             # 只改 seed
        dsp.context.run(main,                      # 全配置
            compute=DType.DUT.INT16,
            strategies=[DataStrategy("random")],
            modes=[Mode.TORCH, Mode.PSEUDO_QUANT],
        )
    """
    runmode = _resolve_runmode(runmode)

    if compute is not None or output_dtype is not None:
        from ..config import config as cfg
        set_compute_config(
            compute=compute or cfg.compute.default_compute,
            output_dtype=output_dtype or cfg.compute.default_output_dtype,
        )

    with _temp_strategies_and_modes(strategies, modes):
        set_global_runmode(runmode, data_path, seed, dut_source=dut_source)
        while not is_global_done():
            result = main_fn()
            submit_output(result)
        export()


def _resolve_runmode(runmode):
    """runmode: 参数 > sys.argv[1] > GENERATE_INPUT。"""
    if runmode is not None:
        return runmode
    import sys
    from ..core.enums import RunMode
    return RunMode(sys.argv[1]) if len(sys.argv) > 1 else RunMode.GENERATE_INPUT


class _temp_strategies_and_modes:
    """临时替换策略和模式列表，退出时还原。"""

    def __init__(self, strategies, modes):
        from ..config import config as cfg
        from ..data.datagen import DataStrategy
        self._strategies = strategies
        if self._strategies is None:
            self._strategies = [
                DataStrategy(**s) if isinstance(s, dict) else s
                for s in cfg.run.strategies
            ]
        self._modes = modes or cfg.run.modes

    def __enter__(self):
        from ..data.datagen import USE_INPUT_MODES, DEFAULT_STRATEGIES
        self._saved_strategies = DEFAULT_STRATEGIES[:]
        self._saved_modes = USE_INPUT_MODES[:]
        DEFAULT_STRATEGIES[:] = self._strategies
        USE_INPUT_MODES[:] = self._modes
        return self

    def __exit__(self, *_):
        from ..data.datagen import USE_INPUT_MODES, DEFAULT_STRATEGIES
        DEFAULT_STRATEGIES[:] = self._saved_strategies
        USE_INPUT_MODES[:] = self._saved_modes


def compare(op_name, a, b, modes=None, **kwargs):
    """用多种模式执行同一操作，对比输出差异。"""
    from ..ops import dispatch
    from ..data.compare import CompareResult, compute_diff

    if modes is None:
        modes = list(VALID_MODES)

    results = {}
    for m in modes:
        with mode_context(m):
            try:
                out = dispatch(op_name, a, b, **kwargs)
                results[m] = out.torch() if hasattr(out, "torch") else out
            except (NotImplementedError, ImportError, RuntimeError):
                results[m] = None

    diffs = {}
    available = [m for m in modes if results.get(m) is not None]
    for i, ma in enumerate(available):
        for mb in available[i + 1:]:
            diffs[(ma, mb)] = compute_diff(results[ma], results[mb])

    return CompareResult(
        op=op_name, modes=modes, results=results, diffs=diffs,
    )
