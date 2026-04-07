"""Linear 算子: out = x @ weight + bias (fused)"""

import torch
from . import register_op
from ..core.enums import Format, DType
from ..golden.manifest import ComputeKey

D, A = DType.DUT, DType.ACC


@register_op(
    weight=Format.NN,
    golden_c={
        ComputeKey(op="linear", in0=D.IQ16, in1=D.IQ16, in2=D.IQ32, out0=D.IQ16, acc=A.Q12_22, compute=D.IQ16):
            "sp_fused_linear_iq16_iq16_biq32_oiq16_acc_q12_22",
        ComputeKey(op="linear", in0=D.IQ16, in1=D.IQ16, in2=D.IQ32, out0=D.IQ32, acc=A.Q12_22, compute=D.IQ16):
            "sp_fused_linear_iq16_iq16_biq32_oiq32_acc_q12_22",
        ComputeKey(op="linear", in0=D.IQ32, in1=D.IQ32, in2=D.IQ32, out0=D.IQ32, acc=A.Q24_40, compute=D.IQ32):
            "sp_fused_linear_iq32_iq32_biq32_oiq32_acc_q24_40",
    },
)
def linear(x: torch.Tensor, weight: torch.Tensor, bias: torch.Tensor) -> torch.Tensor:
    """Linear: out = x @ weight + bias

    参数:
        x: [M, K] 输入矩阵
        weight: [K, N] 权重矩阵（默认 nn 格式，运行时可覆盖）
        bias: [1, N] 或 [N] 偏置向量
    """
    return torch.matmul(x, weight) + bias
