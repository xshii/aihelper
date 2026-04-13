"""共享枚举 — 消灭魔法字符串。

用法:
    from dsp.core.enums import Mode, Format, RunMode

    dsp.context.set_mode(Mode.PSEUDO_QUANT)
    pipe.layout(Format.ZZ)
"""

from enum import Enum


class _StrEnum(str, Enum):
    def __str__(self):
        return self.value

    def __format__(self, format_spec):
        return self.value.__format__(format_spec)


class Mode(_StrEnum):
    TORCH = "torch"
    PSEUDO_QUANT = "pseudo_quant"
    GOLDEN_C = "golden_c"


class Format(_StrEnum):
    ND = "nd"
    ZZ = "zz"
    NN = "nn"


class RunMode(_StrEnum):
    GENERATE_INPUT = "generate_input"
    USE_INPUT = "use_input"
    USE_INPUT_DUT = "use_input_dut"  # DUT 输入+预期输出来自外部，跑 3 种 mode 比数


class TensorSource(_StrEnum):
    """DSPTensor._source — 追踪 tensor 的来源，决定是否需要前置量化。"""
    RANDN = "randn"                      # factory.randn 生成，未量化
    RANDN_QUANTIZED = "randn_quantized"  # 已经过 op 的前置量化
    OP_OUTPUT = "op_output"              # 上游 op 的输出
