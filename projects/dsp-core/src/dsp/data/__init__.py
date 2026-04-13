"""数据管线 — 链式 API 处理 DSP 数据。

不感知算子，只管数据的生成、转换、布局、读写、比对、可视化。

用法:
    import dsp

    # 工厂函数（torch-like）
    x = dsp.data.randn(4, 8, dtype=dsp.core.bf16)
    y = dsp.data.zeros(4, 8, dtype=dsp.core.bf16)

    # 链式处理 + 文件读写
    DataPipe(x, dtype="bf16").layout(dsp.core.Format.ZZ).export("out.txt")
    pipe = dsp.data.load("out.txt")
"""

from .pipe import DataPipe
from .datagen import DataStrategy, DEFAULT_STRATEGIES, generate_by_strategy
from .factory import tensor, zeros, ones, randn, zeros_like, ones_like, from_torch


def load(path):
    """从文件加载 DataPipe。"""
    return DataPipe.load(path)
