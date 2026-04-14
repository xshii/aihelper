"""算子注册 + 分发。

@register_op 装饰器:
    Layer 0: @register_op — 纯 torch，零参数
    Layer 1: @register_op(weight=Format.NN) — 加默认格式标注
    Layer 2: @register_op(golden_c={...}) — 接 golden C
    Layer 3: @register_op(math_strategy=fn) — 数学验证（已知解）

用法:
    @register_op
    def conv2d(input, kernel):
        return torch.nn.functional.conv2d(...)

    @register_op(golden_c={...}, math_strategy=_math_fn, weight=Format.NN)
    def linear(x, weight, bias):
        return torch.matmul(x, weight) + bias

运行时覆盖格式:
    dsp.ops.linear(x, w, b, _formats={"weight": Format.ZZ})
"""

from __future__ import annotations

import functools
import importlib
import inspect
import logging
import pkgutil
import sys
from typing import Callable, Optional

import torch

from ..core.tensor import DSPTensor
from ..core.dtype import DSPDtype
from ..core.enums import Mode, Format, TensorSource

logger = logging.getLogger("dsp.ops")

MATH_STRATEGY_NAME = "math"  # 和 datagen.py 中 DataStrategy("math") 一致


# ============================================================
# 注册表
# ============================================================

_OP_REGISTRY: dict[str, Callable] = {}

# (op_name) → kernel 输出格式 tuple，单输出 op 是长度 1 的 tuple
# 默认 (Format.ZZ,)，只有显式声明 output_fmts= 的 op 才进这个表
_OP_OUTPUT_FMTS: dict[str, tuple[Format, ...]] = {}


def list_ops() -> list[str]:
    return list(_OP_REGISTRY.keys())


def get_output_fmts(op_name: str, n_outputs: int = 1) -> tuple[Format, ...]:
    """查 op 的 kernel 输出 fmt。未声明 → 全部 Format.ZZ。"""
    return _OP_OUTPUT_FMTS.get(op_name, (Format.ZZ,) * n_outputs)


# ============================================================
# 依赖注入（context 启动时注入，ops 不直接 import context）
# ============================================================

_hooks = {
    "get_mode": lambda: Mode.TORCH,
    "is_runmode_active": lambda: False,
    "save_op_inputs": lambda *a, **k: None,
    "save_op_output": lambda *a, **k: None,
    "get_compute_config": lambda: {},
    "get_current_strategy": lambda: None,
    "save_op_expected": lambda *a, **k: None,
    "load_op_inputs": lambda *a, **k: None,
    "get_runmode": lambda: None,
}


def set_ops_hooks(**hooks):
    """由 context 模块注入。ops 不直接 import context。"""
    _hooks.update(hooks)


# ============================================================
# @register_op 装饰器
# ============================================================

def register_op(_func=None, *, golden_c: dict = None, math_strategy: Callable = None,
                output_fmts: tuple = None, **default_formats):
    """注册自定义算子。

    Args:
        _func: 被装饰的函数（@register_op 无参数时）
        golden_c: {ComputeKey: "c_func_name"} 映射，选填
        math_strategy: 数学验证策略函数，选填
            签名: math_strategy(inputs: list, source_map: list[str|None]) -> dict[int, Tensor]
            inputs: 原始参数列表
            source_map: 每个参数的 _source ("randn" | "op_output" | None)
            返回: {arg_index: replacement_tensor} — 只替换 randn 源的参数
        output_fmts: kernel 的输出格式 tuple，选填
            单输出 op: (Format.NN,) 表示 kernel 写出 NN 布局
            多输出 op: (Format.ZZ, Format.NN, Format.ZZ) 每个 output slot 一个
            未声明时所有 output 默认 Format.ZZ
        **default_formats: 参数名→Format 的默认格式标注，选填
            未标注的参数按自动推断（矩阵→zz，向量→nd）

    op_name 自动取函数名。
    output_rules 从 golden_c 的 ComputeKey 自动推导。
    """
    def decorator(func: Callable) -> Callable:
        op_name = func.__name__

        sig = inspect.signature(func)
        param_names = [
            p.name for p in sig.parameters.values()
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]

        # 从 golden_c 的 ComputeKey 自动推导 output_rules
        if golden_c:
            _register_golden_c(op_name, golden_c)

        # 注册 output_fmts (强制 tuple of Format)
        if output_fmts is not None:
            _OP_OUTPUT_FMTS[op_name] = tuple(
                f if isinstance(f, Format) else Format(f) for f in output_fmts
            )

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            runtime_formats = kwargs.pop("_formats", None)
            call_compute = kwargs.pop("compute", None)
            call_output_dtype = kwargs.pop("output_dtype", None)
            active_formats = {**default_formats, **(runtime_formats or {})}

            # --- math strategy 拦截（在 save_op_inputs 之前）---
            args, math_expected = _apply_math_strategy(op_name, math_strategy, args)

            # --- randn 前置量化: 对 randn 来源的 tensor 做 format-aware 量化 ---
            # 把硬件量化误差前置到输入，让 torch 的 double 计算结果接近硬件
            args = _pre_quantize_randn_args(args, param_names, active_formats)

            # --- USE_INPUT / USE_INPUT_DUT 模式: 用磁盘保存的输入替换 args ---
            from ..core.enums import RunMode
            _load_modes = (RunMode.USE_INPUT, RunMode.USE_INPUT_DUT)
            if _hooks["is_runmode_active"]() and _hooks["get_runmode"]() in _load_modes:
                tensor_count = sum(1 for a in args if isinstance(a, torch.Tensor))
                loaded = _hooks["load_op_inputs"](op_name, tensor_count)
                new_args = []
                loaded_idx = 0
                for a in args:
                    if isinstance(a, torch.Tensor):
                        t = loaded[loaded_idx]
                        loaded_idx += 1
                        # 保留 dtype 元信息
                        if isinstance(a, DSPTensor) and a._dsp_dtype is not None:
                            new_args.append(DSPTensor.create(t, a.dsp_dtype))
                        else:
                            new_args.append(t)
                    else:
                        new_args.append(a)
                args = tuple(new_args)

            # --- 出数（通过 hook，不直接 import context）---
            if _hooks["is_runmode_active"]():
                _hooks["save_op_inputs"](op_name, param_names, args, active_formats)

            # --- golden_c ---
            result = None
            if _hooks["get_mode"]() == Mode.GOLDEN_C:
                from ..golden.dispatch import dispatch_golden_c
                # 收集非 tensor 位置参数 + 用户 kwargs，作为 op 参数透传到 call_c_func
                # 例: transpose(x, 0, 2) → op_params={"dim0": 0, "dim1": 2}
                op_params: dict = {}
                for i, a in enumerate(args):
                    if not isinstance(a, torch.Tensor):
                        name = param_names[i] if i < len(param_names) else f"arg{i}"
                        op_params[name] = a
                op_params.update(kwargs)
                result = dispatch_golden_c(
                    op_name, args, _hooks,
                    compute=call_compute,
                    output_dtype=call_output_dtype,
                    op_params=op_params,
                )

            # --- torch / pseudo_quant ---
            if result is None:
                raw_args = [
                    a.torch() if isinstance(a, DSPTensor) else a
                    for a in args
                ]
                result = func(*raw_args, **kwargs)

            # --- 包装结果 ---
            out_dtype = _infer_output_from_args(op_name, args)
            if not isinstance(result, DSPTensor) and out_dtype is not None:
                result = DSPTensor.create(result, out_dtype)

            # --- 标记结果来源 ---
            if isinstance(result, DSPTensor):
                result._source = TensorSource.OP_OUTPUT

            # --- 出数 ---
            if _hooks["is_runmode_active"]():
                _hooks["save_op_output"](op_name, result)
                if math_expected is not None:
                    _hooks["save_op_expected"](op_name, math_expected)

            return result

        # 动态追加 compute / output_dtype 到签名，让 IDE 能看到
        _extra_params = [
            inspect.Parameter("compute", inspect.Parameter.KEYWORD_ONLY, default=None,
                              annotation="str | None"),
            inspect.Parameter("output_dtype", inspect.Parameter.KEYWORD_ONLY, default=None,
                              annotation="str | None"),
        ]
        orig_sig = inspect.signature(func)
        wrapper.__signature__ = orig_sig.replace(
            parameters=[*orig_sig.parameters.values(), *_extra_params]
        )

        _OP_REGISTRY[op_name] = wrapper
        wrapper._dsp_op_name = op_name
        wrapper._dsp_param_names = param_names
        wrapper._dsp_default_formats = default_formats
        wrapper._dsp_math_strategy = math_strategy
        return wrapper

    if _func is not None:
        return decorator(_func)
    return decorator


def dispatch(op_name: str, *args, **kwargs) -> DSPTensor:
    """按名称调用已注册的算子。"""
    fn = _OP_REGISTRY.get(op_name)
    if fn is None:
        from ..core.errors import OpNotRegistered
        raise OpNotRegistered(
            f"算子 '{op_name}' 未注册。已注册: {list(_OP_REGISTRY.keys())}"
        )
    return fn(*args, **kwargs)


# ============================================================
# 内部
# ============================================================

# output type 推导（从 golden_c ComputeKey 自动提取）
_OUTPUT_TYPE_RULES: dict[tuple[str, str, str], str] = {}


def _register_golden_c(op_name: str, golden_c: dict):
    """从 golden_c 映射注册到 manifest + 推导 output_rules。"""
    from ..golden.manifest import COMPUTE, _COMPUTE_BY_OP

    for key, func_name in golden_c.items():
        COMPUTE[key] = func_name
        _COMPUTE_BY_OP.setdefault(key.op, []).append((key, func_name))
        if key.src0 and key.dst0:
            _OUTPUT_TYPE_RULES[(op_name, key.src0, key.src1)] = key.dst0


def _pre_quantize_randn_args(args, param_names, active_formats):
    """对 randn 来源的 tensor 做前置量化。

    流程: pad → to_block → bf16→double (via codec) → from_block → unpad

    只处理 _source == "randn" 的 DSPTensor，非 randn 来源（op_output 等）保留。
    format 从 active_formats[param_name] 取，默认 ZZ。
    """
    from ..core.dtype import get_codec
    from ..core.block import to_block, from_block, pad_to_block

    new_args = []
    for i, arg in enumerate(args):
        if not (isinstance(arg, DSPTensor) and getattr(arg, "_source", None) == TensorSource.RANDN):
            new_args.append(arg)
            continue
        dsp_dtype = arg._dsp_dtype
        if dsp_dtype is None or dsp_dtype.name == "double":
            new_args.append(arg)
            continue

        # 确定 format hint
        name = param_names[i] if i < len(param_names) else None
        fmt = active_formats.get(name, Format.ZZ) if name else Format.ZZ
        if not isinstance(fmt, Format):
            fmt = Format(fmt)

        t = arg.torch()  # (double, no_pad, nd)
        orig_shape = tuple(t.shape)

        if t.ndim >= 2:
            padded = pad_to_block(t, dsp_dtype.name, fmt)
            blocked = to_block(padded, dsp_dtype.name, fmt)
        else:
            blocked = t  # 1D 不做 block 重排

        # double → bf16 → double (走 codec)
        codec = get_codec(dsp_dtype)
        bf16_like = codec.from_double(blocked, dsp_dtype)    # quant: double → bf16
        back = codec.to_double(bf16_like, dsp_dtype)         # dequant: bf16 → double

        if t.ndim >= 2:
            nd = from_block(back, dsp_dtype.name, fmt, tuple(padded.shape))
            nd = nd[..., :orig_shape[-2], :orig_shape[-1]].contiguous()
        else:
            nd = back

        # 保留 DSPTensor 元信息但清除 randn 标记（避免下次再量化）
        new_t = DSPTensor.create(nd, dsp_dtype)
        new_t._source = TensorSource.RANDN_QUANTIZED
        new_args.append(new_t)
    return tuple(new_args)


def infer_output_dtype(op: str, dtype_a: DSPDtype, dtype_b: DSPDtype) -> DSPDtype:
    from ..core.dtype import get_dtype
    key = (op, dtype_a.name, dtype_b.name)
    out_name = _OUTPUT_TYPE_RULES.get(key)
    if out_name is not None:
        return get_dtype(out_name)
    return dtype_a


def _apply_math_strategy(op_name, math_strategy_fn, args):
    """math 轮 + op 有 math_strategy 时替换 randn 源的输入。

    math_strategy_fn 可返回:
      - dict: {idx: tensor} — 只替换输入
      - (dict, expected_tensor) — 替换输入 + 提供期望输出
    返回: (new_args, expected_or_None)
    """
    if math_strategy_fn is None:
        return args, None

    strategy = _hooks["get_current_strategy"]()
    if strategy is None or strategy.name != MATH_STRATEGY_NAME:
        return args, None

    source_map = [
        getattr(a, "_source", None) if isinstance(a, DSPTensor) else None
        for a in args
    ]
    result = math_strategy_fn(list(args), source_map)

    # 解包: dict 或 (dict, expected)
    expected = None
    if isinstance(result, tuple):
        replacements, expected = result
    else:
        replacements = result

    if not replacements:
        logger.debug("[math] %s: no replacements (all args from op_output)", op_name)
        return args, expected

    replaced_indices = sorted(replacements.keys())
    args = list(args)
    for idx, new_tensor in replacements.items():
        args[idx] = new_tensor
    logger.info(
        "[math] %s: replaced %d args (indices %s), sources were %s",
        op_name, len(replacements), replaced_indices,
        [source_map[i] for i in replaced_indices],
    )
    return tuple(args), expected


def _infer_output_from_args(op_name: str, args) -> Optional[DSPDtype]:
    dtypes = []
    for a in args:
        if isinstance(a, DSPTensor) and a._dsp_dtype is not None:
            dtypes.append(a.dsp_dtype)
    if len(dtypes) >= 2:
        return infer_output_dtype(op_name, dtypes[0], dtypes[1])
    if len(dtypes) == 1:
        return dtypes[0]
    return None


# ============================================================
# 内置算子 — 自动扫描 ops/ 下所有 .py 文件，import 即注册
#
# 新增算子只需在 ops/ 下新建 .py 文件，用 @register_op 装饰。
# 调用路径: dsp.ops.linear(x, w, b) → wrapper(x, w, b) → torch/golden_c
# ============================================================

def _auto_import_ops():
    """自动 import ops/ 下所有模块，触发 @register_op 注册。"""
    package = sys.modules[__name__]
    for importer, modname, ispkg in pkgutil.iter_modules(package.__path__):
        if modname.startswith("_"):
            continue
        mod = importlib.import_module(f".{modname}", __name__)
        # 把模块里 @register_op 装饰的函数导出到 ops 命名空间
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if hasattr(obj, "_dsp_op_name"):
                setattr(package, attr_name, obj)

_auto_import_ops()


# ============================================================
# 工厂函数 — 转发到 data/factory.py
# ============================================================

from ..data.factory import tensor, zeros, ones, randn, zeros_like, ones_like, from_torch  # noqa: F401, E402
