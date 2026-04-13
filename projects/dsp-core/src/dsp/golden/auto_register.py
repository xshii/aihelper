"""自动扫描 _raw_bindings 模块的 dsp_* 函数，注册到 manifest。

命名规则:
    dsp_{op}_{dut}                           — 同构 (如 dsp_layernorm1d_bf16)
    dsp_{op}_{dut}_{compute}                 — 同构 + compute type
    dsp_{op}_{dut_a}_dutw_{dut_w}            — 异构 (如 dsp_matmul_bf16_dutw_bf8)
    dsp_{op}_{dut_a}_dutw_{dut_w}_{compute}  — 异构 + compute type
    dsp_convert_{src}_{dst}                  — convert 函数

dutw marker 表示 weight (src1) 使用独立的 DUT 类型；bias (src2) 和输出 (dst0)
跟 input (src0) 同类型。

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
    """解析 binding 函数名 → ComputeKey，写入 COMPUTE + _COMPUTE_BY_OP。"""
    parts = name[len("dsp_"):].split("_")  # e.g. ["matmul","bf16","dutw","bf8","int32"]

    # 1. 尾部 compute type (如 int32)
    if parts and parts[-1] in _COMPUTE_TOKENS:
        parts.pop()

    # 2. 识别 dutw marker
    dut_a = None
    dut_w = None
    if "dutw" in parts:
        idx = parts.index("dutw")
        # 形式: [..., dut_a, "dutw", dut_w]
        if idx >= 1 and idx + 1 < len(parts):
            dut_a_tok = parts[idx - 1]
            dut_w_tok = parts[idx + 1]
            if dut_a_tok in _TYPE_TOKENS and dut_w_tok in _TYPE_TOKENS:
                dut_a = _TYPE_TOKENS[dut_a_tok]
                dut_w = _TYPE_TOKENS[dut_w_tok]
                parts = parts[:idx - 1]  # op 是 dut_a 之前的部分
    else:
        # 3. 同构形式: 尾部一个 DUT token
        if len(parts) >= 2 and parts[-1] in _TYPE_TOKENS:
            dut_a = _TYPE_TOKENS[parts[-1]]
            dut_w = dut_a
            parts.pop()

    if dut_a is None:
        return

    op = "_".join(parts)
    if not op:
        return

    # bias (src2) 和输出 (dst0) 都跟 input 同类型
    key = ComputeKey(op=op, src0=dut_a, src1=dut_w, dst0=dut_a)
    if key not in COMPUTE:
        COMPUTE[key] = name
        _COMPUTE_BY_OP.setdefault(key.op, []).append((key, name))
