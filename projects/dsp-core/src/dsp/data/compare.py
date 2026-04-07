"""CompareMixin — 数据比对能力。

不感知算子，只比较两组数据的差异。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import torch


class CompareMixin:
    """数据比对。"""

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


@dataclass
class CompareResult:
    """比对结果。"""
    diffs: dict = field(default_factory=dict)
    tensor_a: torch.Tensor = None
    tensor_b: torch.Tensor = None
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
            lines.append(
                f"{key}: max_diff={stats['max_diff']:.2e}, "
                f"mean_diff={stats['mean_diff']:.2e}, "
                f"cosine_sim={stats['cosine_sim']:.6f}"
            )
        return "\n".join(lines)

    @property
    def max_diff(self) -> float:
        for stats in self.diffs.values():
            return stats["max_diff"]
        return 0.0

    @property
    def cosine_sim(self) -> float:
        for stats in self.diffs.values():
            return stats["cosine_sim"]
        return 0.0

    def assert_close(self, mode_a: str = None, mode_b: str = None, atol: float = 1e-3):
        """断言两组数据（或两个模式）足够接近。"""
        if mode_a and mode_b:
            # 查 tuple key 或 反向
            diff = self.diffs.get((mode_a, mode_b)) or self.diffs.get((mode_b, mode_a))
            if diff is None:
                raise KeyError(f"未找到 ({mode_a}, {mode_b}) 的对比结果")
            if diff["max_diff"] > atol:
                raise AssertionError(
                    f"{mode_a} vs {mode_b}: max_diff={diff['max_diff']:.2e} > atol={atol:.2e}"
                )
        else:
            for name, stats in self.diffs.items():
                if stats["max_diff"] > atol:
                    raise AssertionError(
                        f"{name}: max_diff={stats['max_diff']:.2e} > atol={atol:.2e}"
                    )


def compute_diff(ta: torch.Tensor, tb: torch.Tensor) -> dict:
    """计算两个 tensor 的差异统计。支持 complex。"""
    if ta.is_complex() or tb.is_complex():
        ra = torch.view_as_real(ta.to(torch.complex64)).flatten()
        rb = torch.view_as_real(tb.to(torch.complex64)).flatten()
    else:
        ra = ta.float().flatten()
        rb = tb.float().flatten()
    diff = (ra - rb).abs()

    cos_sim = torch.nn.functional.cosine_similarity(
        ra.unsqueeze(0), rb.unsqueeze(0)
    ).item()

    return {
        "max_diff": diff.max().item(),
        "mean_diff": diff.mean().item(),
        "cosine_sim": cos_sim,
    }
