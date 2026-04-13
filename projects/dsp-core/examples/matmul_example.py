"""示例：linear (matmul + bias)，非对齐 shape 演示 block padding。

shape 设计（bf16, subblock_size=8, block_shape ZZ=(16,16) NN=(16,32)）:
    x:      [2, 14, 12] bf16 → ZZ 行方向 pad 2 → 16, 列方向 pad 4 → 16
    weight: [12,  8]    bf16 → NN 行方向 pad 4 → 16, 列方向 pad 24 → 32
    bias:   [1,   8]    bf16
    output: [2, 14,  8] bf16

跑完整比数流程（torch → pseudo_quant / golden_c 三路对比）:
    python examples/matmul_example.py                   # 一键完整流程
    python examples/matmul_example.py generate_input    # 只生成
    python examples/matmul_example.py use_input         # 只比数
"""

import sys

import dsp
from dsp.core.enums import RunMode
from dsp.data.datagen import DataStrategy


def matmul(dtype=dsp.core.bf16):
    x = dsp.data.randn(2, 14, 12, dtype=dtype)
    weight = dsp.data.randn(12, 8, dtype=dtype)
    bias = dsp.data.zeros(1, 8, dtype=dtype)
    out = dsp.ops.linear(x, weight, bias)
    return out


if __name__ == "__main__":
    data_path = "output/matmul_demo"
    strategies = [DataStrategy("random")]

    if len(sys.argv) > 1:
        dsp.context.run(matmul, data_path=data_path, seed=42, strategies=strategies)
    else:
        dsp.context.run(matmul, runmode=RunMode.GENERATE_INPUT,
                        data_path=data_path, seed=42, strategies=strategies)
        dsp.context.run(matmul, runmode=RunMode.USE_INPUT,
                        data_path=data_path, seed=42, strategies=strategies)
