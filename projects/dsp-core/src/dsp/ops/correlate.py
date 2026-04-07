"""互相关算子: out[k] = sum_n(signal[n] * conj(template[n+k]))"""

import torch
from . import register_op
from ..core.enums import DType
from ..golden.manifest import ComputeKey

D, A = DType.DUT, DType.ACC


@register_op(golden_c={
    ComputeKey(op="correlate", in0=D.IQ16, in1=D.IQ16, out0=D.IQ32, acc=A.Q12_22, compute=D.IQ16):
        "sp_xcorr_iq16_iq16_oiq32_acc_q12_22",
    ComputeKey(op="correlate", in0=D.IQ32, in1=D.IQ32, out0=D.IQ32, acc=A.Q24_40, compute=D.IQ32):
        "sp_xcorr_iq32_iq32_oiq32_acc_q24_40",
})
def correlate(signal: torch.Tensor, template: torch.Tensor) -> torch.Tensor:
    """互相关。用 conv1d 实现（conv1d 本身就是互相关，不翻转 kernel）。"""
    pad = template.shape[-1] - 1
    if signal.is_complex():
        a_3d = signal.unsqueeze(0).unsqueeze(0)
        b_conj_3d = template.conj().unsqueeze(0).unsqueeze(0)
        ar, ai = a_3d.real, a_3d.imag
        br, bi = b_conj_3d.real, b_conj_3d.imag
        rr = torch.nn.functional.conv1d(ar, br, padding=pad)
        ii = torch.nn.functional.conv1d(ai, bi, padding=pad)
        ri = torch.nn.functional.conv1d(ai, br, padding=pad)
        ir = torch.nn.functional.conv1d(ar, bi, padding=pad)
        return torch.complex((rr + ii).squeeze(), (ri - ir).squeeze())
    else:
        a_3d = signal.unsqueeze(0).unsqueeze(0)
        b_3d = template.unsqueeze(0).unsqueeze(0)
        return torch.nn.functional.conv1d(a_3d, b_3d, padding=pad).squeeze()
