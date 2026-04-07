"""共享枚举 — 消灭魔法字符串。

所有 str Enum: IDE 补全 + 拼错报错 + 序列化友好。

用法:
    from dsp.core.enums import Mode, Format, RunMode, DType

    dsp.context.set_mode(Mode.PSEUDO_QUANT)
    pipe.layout(Format.ZZ)

    DType.DUT.IQ16          # "iq16"
    DType.REAL.FLOAT16      # "float16"
    DType.ACC.Q12_22        # "q12.22"
"""

from enum import Enum


class _StrEnum(str, Enum):
    """str Enum 基类。__str__ 和 __format__ 返回值而不是 'ClassName.MEMBER'。"""
    def __str__(self):
        return self.value

    def __format__(self, format_spec):
        return self.value.__format__(format_spec)


class Mode(_StrEnum):
    """运行模式。"""
    TORCH = "torch"
    PSEUDO_QUANT = "pseudo_quant"
    GOLDEN_C = "golden_c"


class Format(_StrEnum):
    """内存布局格式。"""
    ND = "nd"
    ZZ = "zz"
    NN = "nn"


class RunMode(_StrEnum):
    """验证循环模式。"""
    GENERATE_INPUT = "generate_input"
    USE_INPUT = "use_input"


class DType:
    """分级类型枚举。统一所有类型引用。

    三级:
        DType.REAL  — 标准浮点（torch 原生，也可作为计算精度）
        DType.DUT   — 芯片原生定点（数据存储，也可作为计算精度）
        DType.ACC   — 累加器内部格式（定点，比 DUT 宽）

    弱 AI 新增类型时，在对应的子枚举加一行。
    """

    class REAL(_StrEnum):
        """标准浮点。"""
        FLOAT16 = "float16"
        FLOAT32 = "float32"
        FLOAT64 = "float64"

    class DUT(_StrEnum):
        """芯片原生定点。"""
        IQ16 = "iq16"
        IQ32 = "iq32"

    class ACC(_StrEnum):
        """累加器内部格式。"""
        Q12_22 = "q12.22"
        Q8_26  = "q8.26"
        Q24_40 = "q24.40"
