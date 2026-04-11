"""Linear 算子: out = x @ weight + bias (fused)"""

import logging

import torch
from . import register_op
from ..core.tensor import DSPTensor
from ..core.enums import Format

logger = logging.getLogger("dsp.ops")



# ============================================================
# Math Strategy
# ============================================================

def _near_diagonal(m, n, dtype_torch, scale=1.0, noise=0.01, seed=42):
    """对角 + 小扰动：满秩、条件数低。

    固定 seed 保证同 shape 的 target 在链条中每次调用都一致。
    int 类型先用 float64 构造，再 round+clamp 转换。
    """
    rng = torch.Generator().manual_seed(seed)
    # 始终用 float64 构造
    base = torch.eye(m, n, dtype=torch.float64) * scale
    perturbation = torch.randn(m, n, dtype=torch.float64, generator=rng) * noise
    result = base + perturbation
    if dtype_torch.is_floating_point:
        return result.to(dtype_torch)
    # int 类型: round + clamp + cast
    return result.round().clamp(-32768, 32767).to(dtype_torch)


def _linear_math_strategy(inputs, source_map):
    """linear 数学验证策略。

    设计原则：
    - 首算子（全 randn）：构造 near-diagonal x，设计 w 使输出为 near-diagonal
    - 后续算子（x 来自上游 op_output）：被动接受 x，用 lstsq 设计 w 回归目标 pattern

    inputs: [x, weight, bias]
    source_map: ["randn"|"op_output"|None, ...]
    返回: {arg_index: replacement_tensor}
    """
    x, weight, bias = inputs[0], inputs[1], inputs[2]
    x_from_randn = source_map[0] == "randn"
    bias_from_randn = source_map[2] == "randn"

    # 推断 dtype 信息
    dtype_torch = x.dtype if isinstance(x, torch.Tensor) else torch.float32
    dsp_dtype = x._dsp_dtype if isinstance(x, DSPTensor) else None
    M, K = x.shape[-2], x.shape[-1]
    N = weight.shape[-1]

    # 目标输出 pattern: near-diagonal（seed=42 保证链条中每个 linear 的 target 一致）
    target = _near_diagonal(M, N, dtype_torch, seed=42)
    # 统一用 float64 做 solve
    solve_dtype = torch.float64

    # bias: randn 来源 → 替换为零；op_output 来源 → 保留原值
    if bias_from_randn:
        bias = torch.zeros(1, N, dtype=dtype_torch)

    if x_from_randn:
        # 首算子：重新构造 x（seed=7 避免 x == target 退化）
        new_x = _near_diagonal(M, K, dtype_torch, seed=7)
        # w = lstsq(x, target - bias) 使 x @ w + b ≈ target
        new_weight = torch.linalg.lstsq(
            new_x.to(solve_dtype), (target - bias).to(solve_dtype),
        ).solution.to(dtype_torch)

        logger.debug("[math] linear: first-op, x(%s) w(%s) b(%s)",
                     list(new_x.shape), list(new_weight.shape), list(bias.shape))
        replacements = {
            0: _wrap(new_x, dsp_dtype),
            1: _wrap(new_weight, _get_dsp_dtype(inputs[1])),
        }
    else:
        # 后续算子：x 来自上游，被动接受
        # ridge regression: (X^T X + λI)^{-1} X^T (target - bias) — 防秩亏
        x_s = x.to(solve_dtype).reshape(-1, K)
        rhs = (target - bias).to(solve_dtype)
        lam = 1e-4
        xtx = x_s.T @ x_s + lam * torch.eye(K, dtype=solve_dtype)
        new_weight = torch.linalg.solve(xtx, x_s.T @ rhs).to(dtype_torch)

        logger.debug("[math] linear: subsequent-op (ridge), w(%s) b(%s)",
                     list(new_weight.shape), list(bias.shape))
        replacements = {1: _wrap(new_weight, _get_dsp_dtype(inputs[1]))}

    # bias 只在 randn 来源时替换
    if bias_from_randn:
        replacements[2] = _wrap(bias, _get_dsp_dtype(inputs[2]))

    # expected output = target pattern（用于比数时验证 torch 输出正确性）
    expected = _wrap(target, dsp_dtype)
    return replacements, expected


def _get_dsp_dtype(t):
    return t._dsp_dtype if isinstance(t, DSPTensor) else None


def _wrap(data, dsp_dtype):
    """包装为 DSPTensor（如果有 dsp_dtype）。"""
    if dsp_dtype is not None:
        return DSPTensor.create(data, dsp_dtype)
    return data


# ============================================================
# 算子注册
# ============================================================

@register_op(
    weight=Format.NN,
    math_strategy=_linear_math_strategy,
)
def linear(x: torch.Tensor, weight: torch.Tensor, bias: torch.Tensor) -> torch.Tensor:
    """Linear: out = x @ weight + bias

    参数:
        x: [M, K] 输入矩阵
        weight: [K, N] 权重矩阵（默认 nn 格式，运行时可覆盖）
        bias: [1, N] 或 [N] 偏置向量

    int 类型输入先转 float 计算，结果转回原 dtype。
    """
    orig_dtype = x.dtype
    if not x.dtype.is_floating_point:
        x = x.float()
        weight = weight.float()
        bias = bias.float()
    result = torch.matmul(x, weight) + bias
    if not orig_dtype.is_floating_point:
        result = result.to(orig_dtype)
    return result
