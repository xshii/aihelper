"""框架配置 — 唯一 source of truth，所有默认值在这里。

修改配置直接改这个文件，或运行时覆盖属性。

用法:
    import dsp

    dsp.config.logging.level             # "INFO"
    dsp.config.output.root               # "/abs/path/output/"
    dsp.config.output.seed               # 1
    dsp.config.run.strategies            # [DataStrategy(...), ...]
    dsp.config.run.modes                 # [Mode.TORCH, Mode.PSEUDO_QUANT, Mode.GOLDEN_C]
    dsp.config.compare.pass_cosine       # 0.999

    dsp.config.output.root = "/tmp/my/"  # 运行时覆盖
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# 路径常量 — 弱 AI 用这个，不要用 __file__.parent 反查
GOLDEN_BUILD_DIR = Path(__file__).resolve().parent / "golden" / "build"


@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "%(name)s | %(message)s"


@dataclass
class OutputConfig:
    root: str = ""
    seed: int = 1


@dataclass
class ComputeConfig:
    default_compute: Optional[str] = None
    default_output_dtype: Optional[str] = None


@dataclass
class HWConfig:
    """硬件行为开关 — 集中放所有"不知道真硬件具体怎么做"的可调项。

    golden_c_count_mode: 非对齐输入下，golden_c 接收的"逻辑 count"用哪个值。
        只影响 golden_c 模式；torch / pseudo_quant 永远走数学正确的 reduction。

          - "orig":   传原始逻辑长度（硬件内部 reduction 只在真实数据上走）
                      layernorm 等 reduction-divide-by-count 型 op 的数学正确模式
          - "padded": 传 pad_dim(count, subblock_size) 后的长度
                      硬件会把 padding 区的 0 也纳入 reduction —— 对 linear/matmul
                      等 "0 × x = 0 是恒等元" 的 op 无影响，对 layernorm 有 bias

        默认 "orig" —— 数学正确是最不意外的选择；需要对齐真实硬件行为的话
        显式 `dsp.config.hw.golden_c_count_mode = "padded"`。
    """
    golden_c_count_mode: str = "orig"


@dataclass
class CompareConfig:
    pass_cosine: float = 0.999
    warn_cosine: float = 0.99


@dataclass
class RunConfig:
    """验证循环默认配置。"""
    strategies: list = field(default_factory=lambda: [
        {"name": "math"},
        {"name": "precision_exact", "precision_exact": True, "value_range": (-50, 50)},
        {"name": "random"},
        {"name": "sparse_30", "sparsity": 0.3},
        {"name": "sparse_50", "sparsity": 0.5},
        {"name": "sparse_90", "sparsity": 0.9},
        {"name": "sparse_9999", "sparsity": 0.9999},
        {"name": "corner_all_zero", "sparsity": 1.0},
    ])
    modes: list = field(default_factory=lambda: ["pseudo_quant", "golden_c"])


@dataclass
class DSPConfig:
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    compute: ComputeConfig = field(default_factory=ComputeConfig)
    compare: CompareConfig = field(default_factory=CompareConfig)
    run: RunConfig = field(default_factory=RunConfig)
    hw: HWConfig = field(default_factory=HWConfig)

    def apply_logging(self):
        level = getattr(logging, self.logging.level, logging.INFO)
        logging.basicConfig(level=level, format=self.logging.format, force=True)


# 全局单例
config = DSPConfig()
config.output.root = str(Path("output").resolve())
config.apply_logging()


def get(key: str, default=None):
    """点分路径取值（兼容）: get("output.root") """
    obj = config
    for part in key.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            return default
    return obj
