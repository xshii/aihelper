"""核心类型系统：DSPDtype + DSPTensor + TypeCodec + Enums。"""

from .dtype import (
    DType,
    DSPDtype, bint8, bint16, bint32, double,
    register_dtype, get_dtype, list_dtypes,
    TypeCodec, GoldenCCodec, PassthroughCodec,
    register_codec, get_codec,
)
from .tensor import DSPTensor
from .enums import Mode, Format, RunMode
