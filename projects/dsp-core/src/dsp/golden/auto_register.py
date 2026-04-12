"""自动扫描 _raw_bindings 模块的 dsp_* 函数，注册到 manifest。

命名规则:
    dsp_{op}_{type_parts}           — compute 函数
    dsp_convert_{src_type}_{dst_type} — convert 函数

Python 侧零手动注册：binding 暴露的函数名即 manifest 的 source of truth。
"""

from __future__ import annotations

from ..core.dtype import DType
from .manifest import ComputeKey, COMPUTE, CONVERT, _COMPUTE_BY_OP

# 从枚举自动生成类型 token 映射
# 函数名里用下划线（q12_22），枚举值用点号（q12.22），两种都要能匹配
_TYPE_TOKENS = {}
_TYPE_TOKENS["double"] = "double"
for _enum_cls in (DType.DUT, DType.REAL, DType.ACC):
    for _v in _enum_cls:
        _TYPE_TOKENS[str(_v)] = _v                      # "bint16" → DType.DUT.BINT16
        _TYPE_TOKENS[str(_v).replace(".", "_")] = _v    # "q12_22" → DType.ACC.Q12_22
# convert 函数名里用裸 int16 不用 bint16，也要能匹配
_TYPE_TOKENS["int8"] = DType.DUT.BINT8
_TYPE_TOKENS["int16"] = DType.DUT.BINT16
_TYPE_TOKENS["int32"] = DType.DUT.BINT32

_ACC_MAP = {str(v): v for v in DType.ACC}


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
    suffix = name[len("dsp_convert_"):]  # e.g. "int16_float32"
    types = _extract_types(suffix)
    if len(types) == 2:
        src_name = str(types[0])
        dst_name = str(types[1])
        key = (src_name, dst_name)
        if key not in CONVERT:
            CONVERT[key] = name


def _register_compute(name: str):
    """dsp_{op}_{types} → COMPUTE 表。"""
    parts = name[len("dsp_"):]  # e.g. "matmul_int16_int16_q12_22_q12_22"
    types = _extract_types(parts)
    if not types:
        return

    # op = parts 去掉尾部所有 type tokens 后的剩余
    op = _extract_op(parts)
    if not op:
        return

    key = _build_compute_key(op, types)
    if key is not None and key not in COMPUTE:
        COMPUTE[key] = name
        _COMPUTE_BY_OP.setdefault(key.op, []).append((key, name))


def _extract_types(s: str) -> list:
    """从字符串中提取所有已知类型 token。"""
    types = []
    parts = s.split("_")
    i = 0
    while i < len(parts):
        # 两段: q12_22
        if i + 1 < len(parts):
            two = parts[i] + "_" + parts[i + 1]
            if two in _TYPE_TOKENS:
                types.append(_TYPE_TOKENS[two])
                i += 2
                continue
        # 单段: int16, float32
        if parts[i] in _TYPE_TOKENS:
            types.append(_TYPE_TOKENS[parts[i]])
            i += 1
            continue
        i += 1
    return types


def _extract_op(s: str) -> str:
    """提取 op 名（第一个 type token 之前的部分）。"""
    parts = s.split("_")
    op_parts = []
    for i, p in enumerate(parts):
        # 检查是否是类型开头
        if p in _TYPE_TOKENS:
            break
        if i + 1 < len(parts) and p + "_" + parts[i + 1] in _TYPE_TOKENS:
            break
        op_parts.append(p)
    return "_".join(op_parts) if op_parts else None


def _build_compute_key(op: str, types: list):
    """从类型列表构建 ComputeKey。

    函数名格式: dsp_{op}_{src0}_{src1?}_{src2?}_{dst0}_{acc?}
    最后一个如果是 ACC 格式（Q12_22/Q24_40），作为 acc 字段。
    倒数第二个（去掉 acc 后的最后一个）是 dst0。
    """
    if len(types) < 1:
        return None

    acc = None
    if len(types) >= 2 and str(types[-1]) in _ACC_MAP:
        acc = types.pop()

    # 最后一个是 dst0，之前的都是 src
    dst0 = types.pop() if types else None
    if dst0 is None:
        return None

    # 剩余是 src 参数
    if len(types) == 0:
        # 一元: abs — src0=dst0
        return ComputeKey(op=op, src0=dst0, dst0=dst0, acc=acc)
    elif len(types) == 1:
        # 一元或同类型二元: add_int16 → src0=int16, dst0=int16
        return ComputeKey(op=op, src0=types[0], dst0=dst0, acc=acc)
    elif len(types) == 2:
        return ComputeKey(op=op, src0=types[0], src1=types[1], dst0=dst0, acc=acc)
    elif len(types) == 3:
        return ComputeKey(op=op, src0=types[0], src1=types[1], src2=types[2], dst0=dst0, acc=acc)
    return None
