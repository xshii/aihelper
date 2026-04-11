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
