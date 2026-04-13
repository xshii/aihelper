"""可视化 — 单 pipe 绘图 + 跨模式比数报告。

全部基于 plotly（可选依赖）。

单 pipe 用法:
    pipe.plot()                     # 自动选择图表类型
    pipe.plot(kind="constellation") # 指定类型

比数报告:
    from dsp.data.viz import export_html
    export_html(data_path, report, modes_list)
"""

from __future__ import annotations

import logging
import webbrowser
from datetime import datetime
from pathlib import Path

import torch

logger = logging.getLogger("dsp.data")


def _require_plotly():
    try:
        import plotly  # noqa: F401
    except ImportError:
        raise ImportError("可视化需要 plotly: pip install plotly")


# ============================================================
# Part 1: VizMixin — DataPipe.plot()
# ============================================================

class VizMixin:
    """DataPipe 可视化能力。"""

    def plot(self, kind: str = "auto", **kwargs):
        """可视化当前数据。返回 plotly Figure。

        Args:
            kind: "auto" / "waveform" / "constellation" / "spectrum" / "histogram"
        """
        _require_plotly()
        t = self._tensor.detach().cpu()
        if kind == "auto":
            kind = _auto_kind(t)

        plot_fn = _PIPE_PLOTS.get(kind)
        if plot_fn is None:
            raise ValueError(f"未知类型: '{kind}'。可用: {list(_PIPE_PLOTS)}")

        fig = plot_fn(t, **kwargs)
        self._log(f"plot({kind})")
        return fig


def _auto_kind(t):
    if t.is_complex():
        return "constellation"
    if t.ndim == 1 and t.numel() > 16:
        return "waveform"
    return "histogram"


def _plot_waveform(t, **kwargs):
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=t.numpy(), mode="lines"))
    fig.update_layout(title="Waveform", xaxis_title="index", yaxis_title="value")
    return fig


def _plot_constellation(t, **kwargs):
    import plotly.graph_objects as go
    fig = go.Figure()
    if t.is_complex():
        fig.add_trace(go.Scattergl(
            x=t.real.numpy(), y=t.imag.numpy(),
            mode="markers", marker=dict(size=3, opacity=0.5),
        ))
    else:
        fig.add_trace(go.Scattergl(
            x=t.numpy(), y=[0] * t.numel(),
            mode="markers", marker=dict(size=3),
        ))
    fig.update_layout(title="Constellation", yaxis_scaleanchor="x")
    return fig


def _plot_spectrum(t, **kwargs):
    import plotly.graph_objects as go
    spec = torch.fft.fft(t.float()).abs()
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=spec.numpy(), mode="lines"))
    fig.update_layout(title="Spectrum", xaxis_title="bin", yaxis_title="magnitude")
    return fig


def _plot_histogram(t, **kwargs):
    import plotly.graph_objects as go
    data = t.float().flatten().numpy()
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=data, nbinsx=50))
    fig.update_layout(title="Histogram", xaxis_title="value", yaxis_title="count")
    return fig


_PIPE_PLOTS = {
    "waveform": _plot_waveform,
    "constellation": _plot_constellation,
    "spectrum": _plot_spectrum,
    "histogram": _plot_histogram,
}


# ============================================================
# Part 2: HTML 比数报告
# ============================================================

def export_html(data_path: str, report: dict, modes_list: list[str],
                auto_open: bool = True, runmode: str = "use_input"):
    """生成 HTML 比数报告。文件放 output 根目录，命名含时间戳。

    Args:
        runmode: "use_input" 或 "use_input_dut"，决定 mode 输出文件的查找路径
    """
    try:
        _require_plotly()
    except ImportError:
        logger.warning("plotly 未安装，跳过 HTML 报告。pip install plotly")
        return

    from ..config import config as cfg

    global _plotly_js_included
    _plotly_js_included = False

    parts = [_HTML_HEADER]
    parts.append(_safe_render(_build_summary_table, report, cfg.compare))
    parts.append(_safe_render(_build_strategy_bars, report))
    parts.extend(_build_detail_sections(data_path, report, modes_list, runmode))
    parts.append("</body></html>")

    case_name = Path(data_path).name
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(data_path).parent
    out_path = out_dir / f"compare_{case_name}_{ts}.html"
    out_path.write_text("\n".join(parts))
    logger.info("HTML 报告: %s", out_path)

    if auto_open:
        webbrowser.open(out_path.resolve().as_uri())


# --- 汇总表 ---

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


# --- 策略对比柱状图 ---

def _build_strategy_bars(report: dict) -> str:
    import plotly.graph_objects as go

    pair_data = {}
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


# --- 详情区（折叠） ---

def _build_detail_sections(data_path, report, modes_list, runmode: str):
    """USE_INPUT:     base/<strategy>/<mode>/<fname>
    USE_INPUT_DUT:  base/<mode>/<fname>（无 strategy 层）
    """
    base = Path(data_path) / runmode
    is_dut = runmode == "use_input_dut"
    sections = ['<h2>详情（点击展开）</h2>']

    for strategy, ops in report.items():
        if is_dut:
            mode_dirs = {m: base / m for m in modes_list if (base / m).exists()}
        else:
            mode_dirs = {m: base / strategy / m for m in modes_list
                         if (base / strategy / m).exists()}
        op_parts = []
        for fname in ops:
            tensors = _load_tensors(fname, mode_dirs)
            if len(tensors) < 2:
                continue
            charts = "".join([
                _safe_render(_plot_error_cdf, tensors),
                _safe_render(_plot_bland_altman, tensors),
                _safe_render(_plot_signal_and_error, tensors),
            ])
            if charts:
                op_parts.append(
                    f'<details><summary>{fname}</summary>{charts}</details>'
                )
        if op_parts:
            sections.append(
                f'<details><summary><strong>{strategy}</strong></summary>'
                + "\n".join(op_parts) + '</details>'
            )
    return sections


def _load_tensors(fname, mode_dirs):
    """按 op_id+operand 前缀模糊匹配各模式的输出文件。

    USE_INPUT 时 fname 和实际文件名一致 (`*_double_*_nd.txt`)。
    USE_INPUT_DUT 时 fname 来自 dut_source (`*_bf16_*_zz.txt`)，需要按
    `<op>_<id>_<operand>_*` 前缀匹配各 mode dir 里的 ND 文件。
    """
    from .pipe import DataPipe
    from .io import parse_filename

    meta = parse_filename(fname)
    op = meta.get("op")
    op_id = meta.get("op_id")
    operand = meta.get("operand")
    prefix = f"{op}_{op_id}_{operand}_" if op and op_id is not None and operand else None

    tensors = {}
    for m, d in mode_dirs.items():
        fpath = d / fname
        if not fpath.exists() and prefix:
            matches = list(d.glob(f"{prefix}*.txt"))
            if matches:
                fpath = matches[0]
        if fpath.exists():
            try:
                t = DataPipe.load(str(fpath)).tensor
                if t.is_complex():
                    t = torch.view_as_real(t.to(torch.complex64))
                tensors[m] = t.float().flatten()
            except Exception:
                pass
    return tensors


# --- 误差 CDF ---

def _plot_error_cdf(tensors: dict) -> str:
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
                x=sorted_diff, y=cdf, mode="lines", name=f"{ma} vs {mb}",
            ))
    fig.add_hline(y=0.99, line_dash="dash", line_color="gray",
                  annotation_text="99%")
    fig.update_layout(
        title="误差 CDF（x=阈值, y=元素比例）",
        xaxis_title="abs error", yaxis_title="cumulative ratio",
        height=350, margin=dict(t=40, b=40),
    )
    return _fig_to_div(fig)


# --- Bland-Altman ---

def _plot_bland_altman(tensors: dict) -> str:
    import plotly.graph_objects as go

    modes = list(tensors.keys())
    ref = modes[0]
    fig = go.Figure()
    for m in modes[1:]:
        a, b = tensors[ref].numpy(), tensors[m].numpy()
        fig.add_trace(go.Scattergl(
            x=(a + b) / 2, y=a - b, mode="markers",
            marker=dict(size=3, opacity=0.5), name=f"{ref} vs {m}",
        ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(
        title="Bland-Altman（水平带=随机误差, 喇叭口=幅度相关）",
        xaxis_title="(a + b) / 2", yaxis_title="a - b",
        height=350, margin=dict(t=40, b=40),
    )
    return _fig_to_div(fig)


# --- 信号+误差叠加 ---

def _plot_signal_and_error(tensors: dict) -> str:
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


# --- 共享工具 ---

def _safe_render(render_fn, *args) -> str:
    """容错包裹：渲染失败则跳过，不影响其他图表。"""
    try:
        return render_fn(*args)
    except Exception as e:
        logger.warning("图表渲染失败 (%s): %s", render_fn.__name__, e)
        return ""


_plotly_js_included = False


def _fig_to_div(fig) -> str:
    """第一个图表加载 CDN，后续复用。"""
    global _plotly_js_included
    if not _plotly_js_included:
        _plotly_js_included = True
        return fig.to_html(full_html=False, include_plotlyjs="cdn")
    return fig.to_html(full_html=False, include_plotlyjs=False)


_HTML_HEADER = """<!DOCTYPE html>
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
