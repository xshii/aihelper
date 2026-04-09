"""示例：linear (matmul + bias)。

用法:
    python examples/matmul_example.py                  # 一键：生成数据 → 多模式比数 → 报告
    python examples/matmul_example.py generate_input   # 只生成（torch 模式）
    python examples/matmul_example.py use_input        # 只比数（加载已有数据）
"""

import sys

import dsp
from dsp.core.enums import RunMode


def main():
    x = dsp.data.randn(4, 8, dtype=dsp.core.iq16)
    weight = dsp.data.randn(8, 4, dtype=dsp.core.iq16)
    bias = dsp.data.randn(1, 4, dtype=dsp.core.iq16)
    out = dsp.ops.linear(x, weight, bias)
    print(f"  result: {out.shape}, dtype={out.dsp_dtype}")
    return out


if __name__ == "__main__":
    if len(sys.argv) > 1:
        dsp.context.run(main)
    else:
        dsp.context.run(main, runmode=RunMode.GENERATE_INPUT)
        dsp.context.run(main, runmode=RunMode.USE_INPUT)
