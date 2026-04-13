"""自动扫描 _raw_bindings 模块的 dsp_* 函数，注册到 manifest。

命名规则:
    dsp_{op}_{dut_name}                  — compute 函数 (如 dsp_matmul_bf16)
    dsp_{op}_{dut_name}_{compute_type}   — 带 compute type (如 dsp_layernorm_bf16_int32)
    dsp_convert_{src}_{dst}              — convert 函数

Python 侧零手动注册：binding 暴露的函数名即 manifest 的 source of truth。
"""

from __future__ import annotations

from ..core.dtype import DType
from .manifest import ComputeKey, COMPUTE, CONVERT, _COMPUTE_BY_OP

# 从枚举自动生成类型 token 映射
_TYPE_TOKENS = {}
_TYPE_TOKENS["double"] = "double"
for _enum_cls in (DType.DUT, DType.REAL, DType.ACC):
    for _v in _enum_cls:
        _TYPE_TOKENS[str(_v)] = _v                      # "bf16" → DType.DUT.BF16
        _TYPE_TOKENS[str(_v).replace(".", "_")] = _v    # "q12_22" → DType.ACC.Q12_22

# compute type tokens
_COMPUTE_TOKENS = {"int32", "fp16"}


def auto_register():
    """扫描 _raw_bindings，自动注册所有 dsp_* 函数。"""
    try:
        from .call import _get_lib
        lib = _get_lib()
    except ImportError:
        return

    for name in dir(lib):
        if not name.startswith("dsp_"):
            continue
        if name.startswith("dsp_convert_"):
            _register_convert(name)
        else:
            _register_compute(name)


def _register_convert(name: str):
    """dsp_convert_{src}_{dst} → CONVERT 表。"""
    suffix = name[len("dsp_convert_"):]  # e.g. "double_bf16" or "bf16_double"
    # 从已知 token 里匹配 src 和 dst
    parts = suffix.split("_")
    types = []
    i = 0
    while i < len(parts):
        if i + 1 < len(parts):
            two = parts[i] + "_" + parts[i + 1]
            if two in _TYPE_TOKENS:
                types.append(str(_TYPE_TOKENS[two]))
                i += 2
                continue
        if parts[i] in _TYPE_TOKENS:
            types.append(str(_TYPE_TOKENS[parts[i]]))
        i += 1
    if len(types) == 2:
        key = (types[0], types[1])
        if key not in CONVERT:
            CONVERT[key] = name


def _register_compute(name: str):
    """dsp_{op}_{dut}_{compute_type?} → COMPUTE 表。

    新命名: dsp_matmul_bf16, dsp_layernorm_bf16_int32
    所有输入/输出/bias 都是同一个 DUT 类型。
    """
    parts = name[len("dsp_"):].split("_")  # e.g. ["matmul", "bf16"] or ["layernorm", "bf16", "int32"]

    # 从尾部提取 compute type (如果有)
    if parts and parts[-1] in _COMPUTE_TOKENS:
        parts.pop()  # 去掉尾部的 compute type (如 "int32")

    # 从尾部提取 DUT type
    dut = None
    # 尝试匹配 (如 bf16)
    if len(parts) >= 2:
        candidate = parts[-1]
        if candidate in _TYPE_TOKENS:
            dut = _TYPE_TOKENS[candidate]
            parts.pop()

    if dut is None:
        return

    # 剩余是 op 名
    op = "_".join(parts)
    if not op:
        return

    key = ComputeKey(op=op, src0=dut, dst0=dut)
    if key not in COMPUTE:
        COMPUTE[key] = name
        _COMPUTE_BY_OP.setdefault(key.op, []).append((key, name))
