"""Linear / Matmul 算子 — torch 实现 + C 调用约定 + math strategy。

算子:
    linear:  out = x @ weight + bias (fused)
    matmul:  out = x @ weight

golden_c 预处理由框架接管（见 core/prepare_args.py）:
    - x       : Format.ZZ → 保留 batch 维，last-2-dim pad 到 (bh_zz, bw_zz)，行优先 flatten
    - weight  : Format.NN → 保留 batch 维，last-2-dim pad 到 (bh_nn, bw_nn)，每片列优先 flatten
    - bias    : Format.ND → 1D 向量，末维 pad 到 bh_zz
                由 `bh_zz == bw_nn` 不变式保证 bias 的 pad 长度和 weight 的 col 轴
                pad 后 N 自动一致，不需要额外对齐

Convention 职责:
    C kernel 只认单片 2D 的 (M,K,N)，所以 call_c_func 在 x 或 w 有 batch 维时
    自己 for 循环逐片调 kernel，再 stack 回 batch shape。支持两种场景:
        A. 矩阵复用（w 无 batch）：每次迭代复用同一份 w.flat
        B. 同 loop 维 QK^T（x/w 都有 batch）：batch shape 必须一致，逐片同步切
"""

import numpy as np
import torch

from .. import register_op
from ...core.tensor import DSPTensor
from ...core.enums import Format
from ...core.convention import OpConvention


# ============================================================
# C 调用约定
# ============================================================

def _call_kernel(func, dst, x_flat, w_flat, bias_flat, scale_exp,
                 M: int, K: int, N: int) -> None:
    """按 bias 是否存在分发到 linear / matmul 签名。"""
    if bias_flat is None:
        func(dst, x_flat, w_flat, M, K, N)
    else:
        func(dst, x_flat, w_flat, bias_flat, scale_exp, M, K, N)


def _loop_matmul(func, x, w, bias_flat, scale_exp: int = 0) -> np.ndarray:
    """在 batch 维上 for 循环调 C kernel，collect 2D 结果。

    支持两种 case:
      A. 矩阵复用: x 有 batch，w 是 2D，每次迭代复用 w
      B. 同 loop 维 (QK^T): x 和 w 都有 batch，batch shape 必须一致

    Args:
        func: C kernel
        x: PreparedArg(ZZ)，padded_shape = (*batch_x, M_pad, K_pad)
        w: PreparedArg(NN)，padded_shape = (*batch_w, K_pad, N_pad)
        bias_flat: 已 pad 的 bias flat ndarray（长度 = N_pad）；matmul 传 None
        scale_exp: linear 的 scale_exp；matmul 不用

    Returns:
        ndarray shape (*batch, M_pad, N_pad)，batch = canonical batch shape
    """
    *x_batch, M, K = x.padded_shape
    *w_batch, K_w, N = w.padded_shape
    if K != K_w:
        raise ValueError(
            f"matmul K 轴不一致: x.K={K}, w.K={K_w}; "
            f"同 dtype 下应由 bw_zz==bh_nn 保证相等"
        )

    # ---- 纯 2D × 2D: 直接一次调完 ----
    if not x_batch and not w_batch:
        dst = np.zeros(M * N, dtype=np.double)
        _call_kernel(func, dst, x.flat, w.flat, bias_flat, scale_exp, M, K, N)
        return dst.reshape(M, N)

    # ---- 确定 iteration batch shape（case A / case B / 单侧有 batch）----
    if x_batch and w_batch:
        if tuple(x_batch) != tuple(w_batch):
            raise ValueError(
                f"matmul case B: x.batch={tuple(x_batch)} 与 w.batch={tuple(w_batch)} "
                f"不一致；当前不支持跨 batch 维度 broadcast"
            )
        batch_shape = tuple(x_batch)
    elif x_batch:
        batch_shape = tuple(x_batch)
    else:
        batch_shape = tuple(w_batch)

    B_total = int(np.prod(batch_shape))
    x_batched = x.flat.reshape(B_total, M * K) if x_batch else None
    w_batched = w.flat.reshape(B_total, K * N) if w_batch else None

    results = []
    for i in range(B_total):
        xi = x_batched[i] if x_batched is not None else x.flat
        wi = w_batched[i] if w_batched is not None else w.flat
        dst = np.zeros(M * N, dtype=np.double)
        _call_kernel(func, dst, xi, wi, bias_flat, scale_exp, M, K, N)
        results.append(dst.reshape(M, N))
    return np.stack(results).reshape(*batch_shape, M, N)


class MatmulConvention(OpConvention, op="matmul"):
    """func(dst, input_zz, weight_nn, M, K, N)"""

    def output_shape(self, *inputs, **op_params):
        return (*inputs[0].shape[:-1], inputs[1].shape[-1])

    def call_c_func(self, func, x, w, **_):
        return _loop_matmul(func, x, w, bias_flat=None)


class LinearConvention(OpConvention, op="linear"):
    """func(dst, input_zz, weight_nn, bias, scale_exp, M, K, N)

    bias 声明 Format.ND（1D 向量，框架把 `(1, N)` 包装 auto-squeeze 成 1D）。
    末维 pad 到 `bh_zz`，由 `bh_zz == bw_nn` 不变式保证长度和 weight 的 N 一致，
    直接喂 C kernel。
    """

    def output_shape(self, *inputs, **op_params):
        return (*inputs[0].shape[:-1], inputs[1].shape[-1])

    def call_c_func(self, func, x, w, bias, *, scale_exp=0, **_):
        return _loop_matmul(func, x, w, bias.flat, scale_exp)


# ============================================================
# Math Strategy
# ============================================================

def _near_diagonal(m, n, scale=1.0, noise=0.01, seed=42):
    rng = torch.Generator().manual_seed(seed)
    base = torch.eye(m, n, dtype=torch.double) * scale
    perturbation = torch.randn(m, n, dtype=torch.double, generator=rng) * noise
    return base + perturbation


def _linear_math_strategy(inputs, source_map):
    x, weight, bias = inputs[0], inputs[1], inputs[2]
    from ...core.enums import TensorSource
    x_from_randn = source_map[0] == TensorSource.RANDN
    bias_from_randn = source_map[2] == TensorSource.RANDN

    dsp_dtype = x.dsp_dtype if isinstance(x, DSPTensor) else None
    M, K = x.shape[-2], x.shape[-1]
    N = weight.shape[-1]

    target = _near_diagonal(M, N, seed=42)
    if bias_from_randn:
        bias = torch.zeros(1, N, dtype=torch.double)

    if x_from_randn:
        new_x = _near_diagonal(M, K, seed=7)
        new_weight = torch.linalg.lstsq(new_x, target - bias).solution
        replacements = {
            0: _wrap(new_x, dsp_dtype),
            1: _wrap(new_weight, _get_dsp_dtype(inputs[1])),
        }
    else:
        x_s = x.double().reshape(-1, K)
        rhs = target - bias
        lam = 1e-4
        xtx = x_s.T @ x_s + lam * torch.eye(K, dtype=torch.double)
        new_weight = torch.linalg.solve(xtx, x_s.T @ rhs)
        replacements = {1: _wrap(new_weight, _get_dsp_dtype(inputs[1]))}

    if bias_from_randn:
        replacements[2] = _wrap(bias, _get_dsp_dtype(inputs[2]))

    return replacements, _wrap(target, dsp_dtype)


def _get_dsp_dtype(t):
    return t.dsp_dtype if isinstance(t, DSPTensor) else None


def _wrap(data, dsp_dtype):
    if dsp_dtype is not None:
        return DSPTensor.create(data, dsp_dtype)
    return data


# ============================================================
# 算子注册
# ============================================================

@register_op(
    x=Format.ZZ,
    weight=Format.NN,
    bias=Format.ND,
    math_strategy=_linear_math_strategy,
)
def linear(x: torch.Tensor, weight: torch.Tensor, bias: torch.Tensor) -> torch.Tensor:
    """Linear: out = x @ weight + bias"""
    return torch.matmul(x, weight) + bias


@register_op(x=Format.ZZ, weight=Format.NN)
def matmul(x: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    """Matmul: out = x @ weight（无 bias 版本）"""
    return torch.matmul(x, weight)
