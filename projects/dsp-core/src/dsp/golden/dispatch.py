"""Golden C 调度 — ops 调用 golden 的桥接层。"""

from __future__ import annotations

import torch

from ..core.errors import GoldenNotAvailable
from ..core.tensor import DSPTensor
from .call import compute as golden_compute, is_available


def dispatch_golden_c(op_name: str, args: tuple,
                      hooks: dict,
                      compute=None, output_dtype=None) -> torch.Tensor:
    """golden_c 模式下调 C++ 实现。"""
    if not is_available():
        raise GoldenNotAvailable(f"算子 '{op_name}' 需要 golden C。")

    dsp_args = [a for a in args if isinstance(a, DSPTensor)]
    if len(dsp_args) < 1:
        raise GoldenNotAvailable(f"算子 '{op_name}' 需要至少 1 个 DSPTensor 输入。")

    effective_compute, effective_output = _resolve_precision(hooks, compute, output_dtype)
    type_a, type_b = _extract_types(dsp_args)
    all_np = _args_to_numpy(args)

    info = golden_compute(
        op_name, *all_np, type_a=type_a, type_b=type_b,
        out0=effective_output, compute=effective_compute,
    )
    return torch.from_numpy(info["result"].copy())


def _resolve_precision(hooks, compute, output_dtype):
    """精度选择: 调用参数 > context 默认。"""
    config = hooks["get_compute_config"]()
    return (
        str(compute) if compute else config.get("compute"),
        str(output_dtype) if output_dtype else config.get("output_dtype"),
    )


def _extract_types(dsp_args):
    """从 DSPTensor 列表提取 type_a, type_b。"""
    type_a = dsp_args[0]._dsp_dtype.name
    type_b = dsp_args[1]._dsp_dtype.name if len(dsp_args) > 1 else None
    return type_a, type_b


def _args_to_numpy(args):
    """所有 tensor 参数转 float32 numpy（保持原始 shape）。"""
    import numpy as np
    result = []
    for a in args:
        if isinstance(a, (DSPTensor, torch.Tensor)):
            t = a.torch() if isinstance(a, DSPTensor) else a
            result.append(t.detach().cpu().float().numpy())
    return result
