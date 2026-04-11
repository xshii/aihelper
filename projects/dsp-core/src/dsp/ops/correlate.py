"""互相关算子: out[k] = sum_n(signal[n] * template[n+k])"""

import torch
from . import register_op


@register_op
def correlate(signal: torch.Tensor, template: torch.Tensor) -> torch.Tensor:
    """互相关。用 conv1d 实现（conv1d 本身就是互相关，不翻转 kernel）。

    int 类型输入先转 float 计算，结果转回 float（互相关输出通常更宽）。
    """
    pad = template.shape[-1] - 1
    orig_dtype = signal.dtype
    if not signal.dtype.is_floating_point:
        signal = signal.float()
        template = template.float()
    a_3d = signal.unsqueeze(0).unsqueeze(0)
    b_3d = template.unsqueeze(0).unsqueeze(0)
    result = torch.nn.functional.conv1d(a_3d, b_3d, padding=pad).squeeze()
    if not orig_dtype.is_floating_point:
        result = result.to(orig_dtype)
    return result
