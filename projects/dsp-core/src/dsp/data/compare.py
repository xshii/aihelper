"""CompareMixin + 比对函数 — 数据比对能力。

比对类型:
    compute_diff()       — double 域比对（max_diff, mean_diff, cosine_sim）
    compute_dut_exact()  — DUT bit 精确比对（排除 padding，逐元素）

不感知算子，只比较两组数据的差异。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import torch


# ============================================================
# 比对类型枚举
# ============================================================

class CompareType(Enum):
    """比对方式。"""
    DOUBLE = "double"              # double 域：compute_diff（容忍精度误差）
    DUT_BIT_EXACT = "dut_bit_exact"  # DUT bit 精确：逐元素比对（排除 padding）


# 各 RunMode × Mode 的默认比对规则
# {mode: [CompareType, ...]}
USE_INPUT_COMPARE = {
    "pseudo_quant": [CompareType.DOUBLE],
    "golden_c": [CompareType.DOUBLE],
}

USE_INPUT_DUT_COMPARE = {
    "torch": [CompareType.DOUBLE],
    "pseudo_quant": [CompareType.DOUBLE],
    "golden_c": [CompareType.DUT_BIT_EXACT, CompareType.DOUBLE],
}


# ============================================================
# CompareMixin
# ============================================================

class CompareMixin:
    """数据比对。"""

    # 宿主类提供的属性（DataPipe）
    _tensor: torch.Tensor
    def _log(self, msg: str) -> None: ...

    def compare(self, other) -> CompareResult:
        """和另一个 DataPipe 比对。返回 CompareResult。"""
        diff = compute_diff(self._tensor, other._tensor)
        result = CompareResult(
            diffs={"self vs other": diff},
            tensor_a=self._tensor,
            tensor_b=other._tensor,
        )
        self._log("compare()")
        return result


# ============================================================
# CompareResult
# ============================================================

@dataclass
class CompareResult:
    """比对结果。"""
    diffs: dict = field(default_factory=dict)
    tensor_a: Optional[torch.Tensor] = None
    tensor_b: Optional[torch.Tensor] = None
    # context.compare 使用的额外字段
    op: str = ""
    modes: list = field(default_factory=list)
    results: dict = field(default_factory=dict)

    def __str__(self):
        lines = []
        if self.op:
            lines.append(f"compare({self.op}):")
        for name, stats in self.diffs.items():
            key = f"  {name[0]} vs {name[1]}" if isinstance(name, tuple) else f"  {name}"
            if "match" in stats:
                # DUT bit exact
                status = "PASS" if stats["match"] else "FAIL"
                lines.append(
                    f"{key}: [{status}] "
                    f"mismatches={stats['mismatches']}/{stats['total']}"
                )
            else:
                # double
                qsnr = stats.get("qsnr_db", float("inf"))
                qsnr_str = f"{qsnr:.1f}dB" if qsnr != float("inf") else "inf"
                lines.append(
                    f"{key}: max_diff={stats['max_diff']:.2e}, "
                    f"QSNR={qsnr_str}, "
                    f"cosine_sim={stats['cosine_sim']:.6f}"
                )
        return "\n".join(lines)

    @property
    def max_diff(self) -> float:
        for stats in self.diffs.values():
            if "max_diff" in stats:
                return stats["max_diff"]
        return 0.0

    @property
    def cosine_sim(self) -> float:
        for stats in self.diffs.values():
            if "cosine_sim" in stats:
                return stats["cosine_sim"]
        return 0.0

    def assert_close(self, mode_a: Optional[str] = None, mode_b: Optional[str] = None, atol: float = 1e-3):
        """断言两组数据（或两个模式）足够接近。"""
        if mode_a and mode_b:
            diff = self.diffs.get((mode_a, mode_b)) or self.diffs.get((mode_b, mode_a))
            if diff is None:
                raise KeyError(f"未找到 ({mode_a}, {mode_b}) 的对比结果")
            if "match" in diff:
                if not diff["match"]:
                    raise AssertionError(
                        f"{mode_a} vs {mode_b}: DUT bit mismatch "
                        f"{diff['mismatches']}/{diff['total']}"
                    )
            elif diff["max_diff"] > atol:
                raise AssertionError(
                    f"{mode_a} vs {mode_b}: max_diff={diff['max_diff']:.2e} > atol={atol:.2e}"
                )
        else:
            for name, stats in self.diffs.items():
                if "match" in stats and not stats["match"]:
                    raise AssertionError(
                        f"{name}: DUT bit mismatch {stats['mismatches']}/{stats['total']}"
                    )
                elif "max_diff" in stats and stats["max_diff"] > atol:
                    raise AssertionError(
                        f"{name}: max_diff={stats['max_diff']:.2e} > atol={atol:.2e}"
                    )


# ============================================================
# 比对函数
# ============================================================

def compute_diff(ta: torch.Tensor, tb: torch.Tensor) -> dict:
    """double 域比对：计算两个 tensor 的差异统计。

    Returns:
        {"max_diff", "mean_diff", "cosine_sim", "qsnr_db"}

    QSNR = 10 * log10(signal_power / noise_power)
    signal = ta (参考值), noise = ta - tb
    """
    if ta.is_complex() or tb.is_complex():
        ra = torch.view_as_real(ta.to(torch.complex64)).flatten()
        rb = torch.view_as_real(tb.to(torch.complex64)).flatten()
    else:
        ra = ta.double().flatten()
        rb = tb.double().flatten()

    noise = ra - rb
    diff = noise.abs()

    cos_sim = torch.nn.functional.cosine_similarity(
        ra.unsqueeze(0), rb.unsqueeze(0)
    ).item()

    # QSNR: signal-to-quantization-noise ratio (dB)
    signal_power = (ra * ra).sum()
    noise_power = (noise * noise).sum()
    if noise_power > 0:
        qsnr_db = (10 * torch.log10(signal_power / noise_power)).item()
    else:
        qsnr_db = float("inf")  # 完全一致

    return {
        "type": CompareType.DOUBLE.value,
        "max_diff": diff.max().item(),
        "mean_diff": diff.mean().item(),
        "cosine_sim": cos_sim,
        "qsnr_db": qsnr_db,
    }


def compute_dut_exact(ta: torch.Tensor, tb: torch.Tensor,
                      orig_shape: Optional[tuple] = None) -> dict:
    """DUT bit 精确比对：逐元素比对，排除 padding 区域。

    Args:
        ta: 实际 DUT 输出 tensor
        tb: 预期 DUT 输出 tensor
        orig_shape: 原始 shape（pad 前），None 则全量比对

    Returns:
        {"match": bool, "mismatches": int, "total": int, "first_mismatch": tuple|None}
    """
    # 裁掉 padding：只比有效数据区
    if orig_shape is not None and len(orig_shape) >= 2:
        h, w = orig_shape[-2], orig_shape[-1]
        a = ta[..., :h, :w].contiguous()
        b = tb[..., :h, :w].contiguous()
    else:
        a = ta
        b = tb

    a_flat = a.flatten()
    b_flat = b.flatten()
    total = a_flat.numel()

    mismatches_mask = a_flat != b_flat
    mismatches = mismatches_mask.sum().item()

    first_mismatch = None
    if mismatches > 0:
        idx = int(mismatches_mask.nonzero(as_tuple=True)[0][0].item())
        first_mismatch = (idx, a_flat[idx].item(), b_flat[idx].item())

    return {
        "type": CompareType.DUT_BIT_EXACT.value,
        "match": mismatches == 0,
        "mismatches": mismatches,
        "total": total,
        "first_mismatch": first_mismatch,
    }
