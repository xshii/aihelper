"""Golden C 调度 — ops 调用 golden 的桥接层。

batch 处理:
    C 函数只处理 2D 矩阵。如果输入有 batch 维度（3D+），
    本层按 batch 维度循环调用，再 stack 回原始 batch shape。
"""

from __future__ import annotations

import torch
import numpy as np

from ..core.errors import GoldenNotAvailable
from ..core.tensor import DSPTensor
from .call import compute as golden_compute, is_available
from .manifest import ComputeKey


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
    src0_type, src1_type = _extract_types(dsp_args)
    query = ComputeKey(
        op=op_name, src0=src0_type, src1=src1_type,
        dst0=effective_output, compute_dtype=effective_compute,
    )

    # 检测 batch 维度（第一个参数如果 >2D，按 batch 循环）
    first_arg = args[0]
    first_tensor = first_arg.torch() if isinstance(first_arg, DSPTensor) else first_arg
    batch_shape = first_tensor.shape[:-2] if first_tensor.ndim > 2 else ()

    if len(batch_shape) == 0:
        all_np = _args_to_numpy(args)
        info = golden_compute(*all_np, query=query)
        return torch.from_numpy(info["result"].copy())

    # 有 batch 维度，循环调用
    batch_size = int(np.prod(batch_shape))
    results = []
    for i in range(batch_size):
        batch_args = _slice_batch(args, i)
        all_np = _args_to_numpy(batch_args)
        info = golden_compute(*all_np, query=query)
        results.append(torch.from_numpy(info["result"].copy()))

    stacked = torch.stack(results)
    return stacked.reshape(*batch_shape, *results[0].shape)


def _slice_batch(args, batch_idx):
    """从 batch 维度取一个 slice。只对 >2D 的 tensor 切片，<=2D 的原样保留。"""
    sliced = []
    for a in args:
        t = a.torch() if isinstance(a, DSPTensor) else a
        if isinstance(t, torch.Tensor) and t.ndim > 2:
            # 按 batch 维度切片，保留最后 2 维
            flat = t.reshape(-1, *t.shape[-2:])
            s = flat[batch_idx]
            if isinstance(a, DSPTensor):
                s = DSPTensor.create(s, a._dsp_dtype)
            sliced.append(s)
        else:
            sliced.append(a)
    return tuple(sliced)


def _resolve_precision(hooks, compute, output_dtype):
    """精度选择: 调用参数 > context 默认。"""
    config = hooks["get_compute_config"]()
    return (
        str(compute) if compute else config.get("compute"),
        str(output_dtype) if output_dtype else config.get("output_dtype"),
    )


def _extract_types(dsp_args):
    """从 DSPTensor 列表提取 src0_type, src1_type。"""
    src0_type = dsp_args[0]._dsp_dtype.name
    src1_type = dsp_args[1]._dsp_dtype.name if len(dsp_args) > 1 else None
    return src0_type, src1_type


def _args_to_numpy(args):
    """所有 tensor 参数转 float32 numpy。"""
    result = []
    for a in args:
        if isinstance(a, (DSPTensor, torch.Tensor)):
            t = a.torch() if isinstance(a, DSPTensor) else a
            result.append(t.detach().cpu().float().numpy())
    return result
