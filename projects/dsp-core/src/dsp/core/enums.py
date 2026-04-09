"""共享枚举 — 消灭魔法字符串。

用法:
    from dsp.core.enums import Mode, Format, RunMode, DType

    dsp.context.set_mode(Mode.PSEUDO_QUANT)
    pipe.layout(Format.ZZ)

    DType.DUT.INT16         # "int16"
    DType.REAL.FLOAT32      # "float32"
    DType.ACC.INT32         # "int32"
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


class DType:
    """分级类型枚举。

    DType.REAL — 标准浮点（参考计算用）
    DType.DUT  — 芯片原生定点（数据存储）
    DType.ACC  — 累加器格式（比 DUT 宽）
    """

    class REAL(_StrEnum):
        FLOAT32 = "float32"
        FLOAT64 = "float64"

    class DUT(_StrEnum):
        INT8 = "int8"
        INT16 = "int16"

    class ACC(_StrEnum):
        INT32 = "int32"
        Q12_22 = "q12.22"
        Q8_26  = "q8.26"
        Q24_40 = "q24.40"
