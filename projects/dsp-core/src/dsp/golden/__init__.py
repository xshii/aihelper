"""Golden C 封装 — 屏蔽底层 C++ 接口的混乱。

对外只暴露三个动词:
    golden.convert(data, src_type, dst_type)   — 类型转换
    golden.compute(op, a, b, type_a, type_b)   — 计算
    golden.info(dtype_name)                    — 查类型信息

所有硬件细节（函数名、block shape、累加精度）封装在 manifest.py 中。
"""

from .manifest import (
    get_type_info as info,
    get_block_shape,
    list_types,
    list_ops,
    list_converts,
    get_compute_info,
)
from .call import convert, compute, is_available

# 注入 golden.convert 到 core.codec（解除 core→golden 依赖）
from ..core.dtype import GoldenCCodec
GoldenCCodec.set_golden_converter(convert, is_available)

# 自动扫描 _raw_bindings 的 dsp_* 函数，注册到 manifest
from .auto_register import auto_register
auto_register()
