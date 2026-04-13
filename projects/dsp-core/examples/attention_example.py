"""示例：简化 Attention — torch / pseudo_quant / golden_c 三路比数

非对齐 shape: batch=2, M=12, K=14, D=20

三阶段完整流程:
    1. GENERATE_INPUT: torch 生成输入 + 参考输出，写 ND 文件
    2. USE_INPUT:      读 ND，pseudo_quant + golden_c 各跑一次并横比
    3. USE_INPUT_DUT:  把上一步 golden_c 产出的 dut/ 文件当成"外部硬件输出"，
                       从 bf16 bits 还原 double 输入，三种模式各跑一遍

用法:
    python examples/attention_example.py                # 一键完整流程
    python examples/attention_example.py generate_input # 只生成
    python examples/attention_example.py use_input      # 只重放 + 比数
"""

import sys
from pathlib import Path

import dsp
from dsp.core.enums import RunMode
from dsp.data.datagen import DataStrategy


def attention(dtype=dsp.core.bf16):
    """简化 attention: QKV → transpose → matmul → layernorm。"""
    B, M, K, D = 2, 12, 14, 20

    input_t = dsp.data.randn(B, M, K, dtype=dtype)

    Wq = dsp.data.randn(K, D, dtype=dtype)
    Wk = dsp.data.randn(K, D, dtype=dtype)
    Wv = dsp.data.randn(K, D, dtype=dtype)
    zero_d = dsp.data.zeros(1, D, dtype=dtype)

    Q = dsp.ops.linear(input_t, Wq, zero_d)
    K_out = dsp.ops.linear(input_t, Wk, zero_d)
    V = dsp.ops.linear(input_t, Wv, zero_d)

    KT = dsp.ops.transpose(K_out)

    zero_mm = dsp.data.zeros(1, M, dtype=dtype)
    attn = dsp.ops.linear(Q, KT, zero_mm)

    out = dsp.ops.linear(attn, V, zero_d)

    # layernorm1d: 按最后一维 normalize
    # out.shape = (B=2, M=12, D=20) → rows = B*M = 24 个独立 token，每个在 D=20 上 normalize
    # cols=20 不是 subblock_size=8 的整数倍 —— 触发 hw.golden_c_count_mode 开关语义差异
    gamma = dsp.data.ones(D, dtype=dtype)
    beta = dsp.data.zeros(D, dtype=dtype)
    return dsp.ops.layernorm1d(out, gamma, beta)


def _latest_case_dir(data_path: str) -> Path:
    """返回 data_path 下最新（按 mtime）的 case 目录。"""
    root = Path(data_path)
    return max((d for d in root.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime)


if __name__ == "__main__":
    data_path = "output/attention_demo"
    strategies = [DataStrategy("random")]

    if len(sys.argv) > 1:
        dsp.context.run(attention, data_path=data_path, seed=42, strategies=strategies)
        sys.exit(0)

    # 阶段 1: GENERATE_INPUT — torch 生成 ND 文件
    dsp.context.run(attention, runmode=RunMode.GENERATE_INPUT,
                    data_path=data_path, seed=42, strategies=strategies)

    # 阶段 2: USE_INPUT — pseudo_quant + golden_c 重放，golden_c 顺便写 dut/
    dsp.context.run(attention, runmode=RunMode.USE_INPUT,
                    data_path=data_path, seed=42, strategies=strategies)

    # 阶段 3: USE_INPUT_DUT — 把上一步 golden_c 写的 dut/ 文件当作"外部硬件输出"
    # 路径 A demo: dut_source 指向 use_input/random/golden_c/dut
    # 路径 B（真实硬件）: dut_source 指向硬件产物目录即可，无需跑前两阶段
    case_dir = _latest_case_dir(data_path)
    dut_source = case_dir / "use_input" / "random" / "golden_c" / "dut"
    if dut_source.exists():
        dsp.context.run(
            attention, runmode=RunMode.USE_INPUT_DUT,
            data_path=data_path, seed=42,
            dut_source=str(dut_source),
        )
