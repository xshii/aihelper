"""数据管线 — 链式 API 处理 DSP 数据。

不感知算子，只管数据的生成、转换、布局、读写、比对、可视化。

用法:
    import dsp

    # 链式处理
    pipe = (dsp.data.from_tensor(x, dtype="int16")
        .convert("float32")
        .layout("zz")
        .export("output.txt"))

    # 加载 + 比对
    diff = dsp.data.load("torch_out.txt").compare(dsp.data.load("golden_out.txt"))

    # 生成测试数据
    t = dsp.data.generate(4, 8, strategy="random", dtype_torch=torch.float32)
"""

from .pipe import DataPipe
from .datagen import DataStrategy, DEFAULT_STRATEGIES, generate_by_strategy
from .factory import tensor, zeros, ones, randn, zeros_like, ones_like, from_torch
from ..core.enums import Format


def from_tensor(t, dtype=None, fmt=Format.ND):
    """从 torch.Tensor 创建 DataPipe。"""
    return DataPipe(t, dtype=dtype, fmt=fmt)


def load(path):
    """从文件加载 DataPipe。"""
    return DataPipe.load(path)


def generate(*size, strategy="random", dtype_torch=None):
    """按策略生成数据，返回 torch.Tensor。"""
    import torch
    dtype_torch = dtype_torch or torch.float32
    if isinstance(strategy, str):
        strat = next((s for s in DEFAULT_STRATEGIES if s.name == strategy), None)
        if strat is None:
            strat = DataStrategy(strategy)
    else:
        strat = strategy
    return generate_by_strategy(*size, dtype_torch=dtype_torch, strategy=strat)
