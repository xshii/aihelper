"""示例：linear (matmul + bias)。

用法:
    python examples/matmul_example.py                  # 默认 generate_input
    python examples/matmul_example.py use_input
"""

import dsp


def main():
    x = dsp.data.randn(4, 8, dtype=dsp.core.iq16)
    weight = dsp.data.randn(8, 4, dtype=dsp.core.iq16)
    bias = dsp.data.randn(1, 4, dtype=dsp.core.iq16)
    out = dsp.ops.linear(x, weight, bias)
    print(f"  result: {out.shape}, dtype={out.dsp_dtype}")
    return out


if __name__ == "__main__":
    dsp.context.run(main)
