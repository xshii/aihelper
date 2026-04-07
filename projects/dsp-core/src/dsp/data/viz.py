"""VizMixin — 可视化能力。

matplotlib 可选依赖。未安装时 import 不报错，调用 plot 时才报错。
"""

from __future__ import annotations


class VizMixin:
    """数据可视化。"""

    def plot(self, kind: str = "auto", **kwargs):
        """可视化当前数据。返回 (fig, axes)。

        Args:
            kind: "auto" / "waveform" / "constellation" / "spectrum" / "histogram"

        Example:
            pipe.plot()                    # 自动选择
            pipe.plot(kind="constellation") # 指定类型
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError("可视化需要 matplotlib: pip install matplotlib")

        t = self._tensor.detach().cpu()

        if kind == "auto":
            kind = _auto_kind(t)

        _PLOT_DISPATCH = {
            "waveform": _plot_waveform,
            "constellation": _plot_constellation,
            "spectrum": _plot_spectrum,
            "histogram": _plot_histogram,
        }
        plot_fn = _PLOT_DISPATCH.get(kind)
        if plot_fn is None:
            raise ValueError(f"未知可视化类型: '{kind}'。可用: {list(_PLOT_DISPATCH)}")

        fig, axes = plot_fn(t, **kwargs)
        self._log(f"plot({kind})")
        return fig, axes


def _auto_kind(t):
    if t.is_complex():
        return "constellation"
    if t.ndim == 1 and t.numel() > 16:
        return "waveform"
    return "histogram"


def _plot_waveform(t, **kwargs):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.plot(t.numpy())
    ax.set_title("Waveform")
    return fig, ax


def _plot_constellation(t, **kwargs):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    if t.is_complex():
        ax.scatter(t.real.numpy(), t.imag.numpy(), s=2, alpha=0.5)
    else:
        ax.scatter(t.numpy(), [0] * t.numel(), s=2)
    ax.set_title("Constellation")
    ax.set_aspect("equal")
    return fig, ax


def _plot_spectrum(t, **kwargs):
    import matplotlib.pyplot as plt
    import torch
    fig, ax = plt.subplots()
    spec = torch.fft.fft(t.float()).abs()
    ax.plot(spec.numpy())
    ax.set_title("Spectrum")
    return fig, ax


def _plot_histogram(t, **kwargs):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    data = t.float().flatten().numpy()
    ax.hist(data, bins=50)
    ax.set_title("Histogram")
    return fig, ax
