"""示例：linear (matmul + bias)，非对齐 shape 演示 block padding。

shape 设计:
    x:      [2, 14, 12] int16 → zz block (16,16) → pad 2行 + 4列
    weight: [12, 8]     int16 → nn block (16,32) → pad 4行 + 24列
    bias:   [1, 8]      int16
    output: [2, 14, 8]  int32(ACC) → zz block (8,8) → pad 2行 + 0列

用法:
    python examples/matmul_example.py                  # 一键：生成 → 比数 → 报告
    python examples/matmul_example.py generate_input   # 只生成（torch 模式）
    python examples/matmul_example.py use_input        # 只比数（加载已有数据）
"""

import sys

import dsp
from dsp.core.enums import RunMode


def main():
    x = dsp.data.randn(2, 14, 12, dtype=dsp.core.bint16)
    weight = dsp.data.randn(12, 8, dtype=dsp.core.bint16)
    bias = dsp.data.randn(1, 8, dtype=dsp.core.bint16)
    out = dsp.ops.linear(x, weight, bias)
    print(f"  x:      {list(x.shape)}, dtype={x.dsp_dtype}")
    print(f"  weight: {list(weight.shape)}, dtype={weight.dsp_dtype}")
    print(f"  bias:   {list(bias.shape)}, dtype={bias.dsp_dtype}")
    print(f"  output: {list(out.shape)}, dtype={out.dsp_dtype}")
    return out


if __name__ == "__main__":
    if len(sys.argv) > 1:
        dsp.context.run(main)
    else:
        dsp.context.run(main, runmode=RunMode.GENERATE_INPUT)
        dsp.context.run(main, runmode=RunMode.USE_INPUT)
