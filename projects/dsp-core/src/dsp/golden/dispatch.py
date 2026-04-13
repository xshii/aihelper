"""Golden C 调度 — ops 调用 golden 的桥接层。

batch 处理由各 op 的 convention 自己负责。
"""

from __future__ import annotations

import torch

from ..core.errors import ManifestNotFound
from ..core.tensor import DSPTensor
from .call import compute as golden_compute, is_available
from .manifest import ComputeKey


def dispatch_golden_c(op_name: str, args: tuple,
                      hooks: dict,
                      compute=None, output_dtype=None) -> torch.Tensor | None:
    """golden_c 模式下调 C++ 实现。找不到匹配时返回 None（fallback 到 torch）。"""
    if not is_available():
        return None

    dsp_args = [a for a in args if isinstance(a, DSPTensor)]
    if len(dsp_args) < 1:
        return None

    effective_compute, effective_output = _resolve_precision(hooks, compute, output_dtype)
    query = _build_query(op_name, dsp_args,
                         compute_dtype=effective_compute,
                         output_dtypes=effective_output)

    try:
        all_np = _args_to_numpy(args)
        info = golden_compute(*all_np, query=query)
        return torch.from_numpy(info["result"].copy())
    except ManifestNotFound:
        return None


def _build_query(op_name: str, dsp_args: list,
                 compute_dtype: str | None = None,
                 output_dtypes: str | list[str] | None = None) -> ComputeKey:
    """从实际输入构建 ComputeKey 查询。"""
    src = [a.dsp_dtype.name for a in dsp_args]
    if isinstance(output_dtypes, str):
        output_dtypes = [output_dtypes]
    dst = output_dtypes or []

    return ComputeKey(
        op=op_name,
        src0=src[0] if len(src) > 0 else None,
        src1=src[1] if len(src) > 1 else None,
        src2=src[2] if len(src) > 2 else None,
        dst0=dst[0] if len(dst) > 0 else None,
        dst1=dst[1] if len(dst) > 1 else None,
        dst2=dst[2] if len(dst) > 2 else None,
        compute_dtype=compute_dtype,
    )


def _resolve_precision(hooks, compute, output_dtype):
    """精度选择: 调用参数 > context 默认。"""
    config = hooks["get_compute_config"]()
    return (
        str(compute) if compute else config.get("compute"),
        str(output_dtype) if output_dtype else config.get("output_dtype"),
    )


def _args_to_numpy(args):
    """所有 tensor 参数转 double numpy。"""
    result = []
    for a in args:
        if isinstance(a, (DSPTensor, torch.Tensor)):
            t = a.torch() if isinstance(a, DSPTensor) else a
            result.append(t.detach().cpu().double().numpy())
    return result
