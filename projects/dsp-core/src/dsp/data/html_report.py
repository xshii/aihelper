"""HTML 比数报告 — Plotly 交互式，自包含单文件。

五部分：
1. 汇总表：策略 × 模式对 → PASS/WARN/FAIL
2. 策略对比柱状图：哪种策略误差最大
3. 误差 CDF：多少比例的元素在阈值内
4. Bland-Altman：误差和信号幅度的关系
5. 信号+误差叠加：逐元素定位
"""

from __future__ import annotations

import logging
from pathlib import Path

import torch

logger = logging.getLogger("dsp.data")


def export_html(data_path: str, report: dict, modes_list: list[str]):
    """生成 HTML 比数报告。"""
    try:
        import plotly  # noqa: F401
    except ImportError:
        logger.warning("plotly 未安装，跳过 HTML 报告。pip install plotly")
        return

    from ..config import config as cfg

    parts = [_HEADER]
    parts.append(_build_summary_table(report, cfg.compare))
    parts.append(_build_strategy_bars(report))
    parts.extend(_build_detail_sections(data_path, report, modes_list))
    parts.append("</body></html>")

    out_path = Path(data_path) / "report.html"
    out_path.write_text("\n".join(parts))
    logger.info("HTML 报告: %s", out_path)


# ============================================================
# 1. 汇总表
# ============================================================

def _build_summary_table(report: dict, compare_cfg) -> str:
    pass_cos = compare_cfg.pass_cosine
    warn_cos = compare_cfg.warn_cosine
    rows = []
    for strategy, ops in report.items():
        for fname, pairs in ops.items():
            for pair_name, stats in pairs.items():
                status = _status(stats, pass_cos, warn_cos)
                rows.append(
                    f'<tr><td>{strategy}</td><td>{fname}</td>'
                    f'<td>{pair_name}</td>'
                    f'<td>{stats["max_diff"]:.2e}</td>'
                    f'<td>{stats["cosine_sim"]:.6f}</td>'
                    f'<td class="{status.lower()}">{status}</td></tr>'
                )
    return (
        '<h2>汇总</h2>'
        '<table><tr><th>策略</th><th>输出</th><th>对比</th>'
        '<th>max_diff</th><th>cosine</th><th>状态</th></tr>'
        + "\n".join(rows) + '</table>'
    )


def _status(stats, pass_cos, warn_cos):
    if stats["max_diff"] == 0:
        return "PASS"
    if stats["cosine_sim"] > pass_cos:
        return "PASS"
    return "WARN" if stats["cosine_sim"] > warn_cos else "FAIL"


# ============================================================
# 2. 策略对比柱状图
# ============================================================

def _build_strategy_bars(report: dict) -> str:
    """每个模式对一组柱子，x=策略，y=max_diff。"""
    import plotly.graph_objects as go

    pair_data = {}  # {pair_name: {strategy: max_diff}}
    for strategy, ops in report.items():
        for pairs in ops.values():
            for pair_name, stats in pairs.items():
                pair_data.setdefault(pair_name, {})[strategy] = stats["max_diff"]

    fig = go.Figure()
    for pair_name, strats in pair_data.items():
        fig.add_trace(go.Bar(
            x=list(strats.keys()), y=list(strats.values()), name=pair_name,
        ))
    fig.update_layout(
        title="策略对比: 哪种数据模式误差最大",
        yaxis_title="max_diff", barmode="group", height=350,
        margin=dict(t=40, b=40),
    )
    return '<h2>策略对比</h2>' + _fig_to_div(fig)


# ============================================================
# 3-5. 详情区（CDF + Bland-Altman + 信号叠加）
# ============================================================

def _build_detail_sections(data_path, report, modes_list):
    """渐进式披露：每个策略一个折叠区，每个输出文件一个子折叠。"""
    from ..core.enums import RunMode
    base = Path(data_path) / RunMode.USE_INPUT
    sections = ['<h2>详情（点击展开）</h2>']

    for strategy, ops in report.items():
        mode_dirs = {m: base / strategy / m for m in modes_list
                     if (base / strategy / m).exists()}
        op_sections = []
        for fname in ops:
            tensors = _load_tensors(fname, mode_dirs)
            if len(tensors) < 2:
                continue
            op_sections.append(
                f'<details><summary>{fname}</summary>'
                + _plot_error_cdf(tensors)
                + _plot_bland_altman(tensors)
                + _plot_signal_and_error(tensors)
                + '</details>'
            )
        if op_sections:
            sections.append(
                f'<details><summary><strong>{strategy}</strong></summary>'
                + "\n".join(op_sections)
                + '</details>'
            )
    return sections


def _load_tensors(fname, mode_dirs):
    from .pipe import DataPipe
    tensors = {}
    for m, d in mode_dirs.items():
        fpath = d / fname
        if fpath.exists():
            try:
                tensors[m] = DataPipe.load(str(fpath)).tensor.float().flatten()
            except Exception:
                pass
    return tensors


# ============================================================
# 图表
# ============================================================

def _plot_error_cdf(tensors: dict) -> str:
    """误差 CDF：x=误差阈值，y=比例。一眼看合规。"""
    import plotly.graph_objects as go
    import numpy as np

    modes = list(tensors.keys())
    fig = go.Figure()
    for i, ma in enumerate(modes):
        for mb in modes[i + 1:]:
            diff = (tensors[ma] - tensors[mb]).abs().numpy()
            sorted_diff = np.sort(diff)
            cdf = np.arange(1, len(sorted_diff) + 1) / len(sorted_diff)
            fig.add_trace(go.Scatter(
                x=sorted_diff, y=cdf, mode="lines",
                name=f"{ma} vs {mb}",
            ))
    fig.add_hline(y=0.99, line_dash="dash", line_color="gray",
                  annotation_text="99%")
    fig.update_layout(
        title="误差 CDF（x=阈值, y=元素比例）",
        xaxis_title="abs error", yaxis_title="cumulative ratio",
        height=350, margin=dict(t=40, b=40),
    )
    return _fig_to_div(fig)


def _plot_bland_altman(tensors: dict) -> str:
    """Bland-Altman: x=均值, y=差值。喇叭口=幅度相关误差。"""
    import plotly.graph_objects as go

    modes = list(tensors.keys())
    ref = modes[0]
    fig = go.Figure()
    for m in modes[1:]:
        a, b = tensors[ref].numpy(), tensors[m].numpy()
        mean_val = (a + b) / 2
        diff_val = a - b
        fig.add_trace(go.Scattergl(
            x=mean_val, y=diff_val, mode="markers",
            marker=dict(size=3, opacity=0.5),
            name=f"{ref} vs {m}",
        ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(
        title="Bland-Altman（水平带=随机误差, 喇叭口=幅度相关）",
        xaxis_title="(a + b) / 2", yaxis_title="a - b",
        height=350, margin=dict(t=40, b=40),
    )
    return _fig_to_div(fig)


def _plot_signal_and_error(tensors: dict) -> str:
    """信号叠加 + 误差图。"""
    from plotly.subplots import make_subplots
    import plotly.graph_objects as go

    modes = list(tensors.keys())
    ref = modes[0]
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        subplot_titles=["各模式输出叠加", f"误差 (相对 {ref})"],
        vertical_spacing=0.12,
    )
    for m in modes:
        fig.add_trace(go.Scatter(
            y=tensors[m].numpy(), name=m, mode="lines", line=dict(width=1),
        ), row=1, col=1)
    for m in modes[1:]:
        err = (tensors[m] - tensors[ref]).numpy()
        fig.add_trace(go.Scatter(
            y=err, name=f"{m} - {ref}", mode="lines", line=dict(width=1),
        ), row=2, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)
    fig.update_layout(height=500, margin=dict(t=40, b=40))
    fig.update_xaxes(title_text="element index", row=2, col=1)
    return _fig_to_div(fig)


def _fig_to_div(fig) -> str:
    return fig.to_html(full_html=False, include_plotlyjs="cdn")


# ============================================================
# HTML
# ============================================================

_HEADER = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>DSP 比数报告</title>
<style>
body { font-family: -apple-system, sans-serif; margin: 2em; color: #333; max-width: 1200px; }
h2 { border-bottom: 2px solid #ccc; padding-bottom: 0.3em; }
h3 { color: #555; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; }
th, td { border: 1px solid #ddd; padding: 6px 10px; text-align: left; font-size: 13px; }
th { background: #f5f5f5; }
.pass { color: #2e7d32; font-weight: bold; }
.warn { color: #f57f17; font-weight: bold; }
.fail { color: #c62828; font-weight: bold; }
details { margin: 0.5em 0; border: 1px solid #e0e0e0; border-radius: 4px; padding: 0.5em; }
details > summary { cursor: pointer; font-size: 14px; padding: 0.3em; }
details > details { margin-left: 1em; }
</style>
</head><body>
<h1>DSP 比数报告</h1>"""
