"""dsp — 统一 DSP 前端。

模块:
    core     — DSPDtype + DSPTensor + Enums
    golden   — C++ 封装（manifest + convert/compute）
    data     — 数据管线（DataPipe 链式 API + 工厂函数）
    ops      — 算子（@register_op + torch 实现）
    context  — 上下文（模式切换 + 验证循环）
    config   — 框架配置（config.yaml）

用法:
    import dsp

    a = dsp.data.randn(4, 8, dtype=dsp.core.bint16)
    out = dsp.ops.linear(a, weight, bias)

    dsp.context.set_mode(Mode.PSEUDO_QUANT)
    dsp.context.set_global_runmode(RunMode.GENERATE_INPUT)
"""

from .config import config, get as get_config  # 最先加载，初始化日志
from . import core, golden, data, ops, context
