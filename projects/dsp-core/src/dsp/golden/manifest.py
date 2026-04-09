"""Golden C 声明表 — 所有硬件相关信息的唯一 source of truth。

本文件由人（或强 AI）维护，不做自动推断。
弱 AI 新增类型/算子时，只需要往这三张表加行。

三张表:
  TYPES    — 硬件数据类型：C 命名、block shape
  CONVERT  — 类型转换函数：(src, dst) → C 函数名
  COMPUTE  — 计算函数：ComputeKey → C 函数名

设计原则:
  - 显式胜于隐式：每个 C 函数名都明确写出来，不靠命名规则猜
  - 屏蔽底层格式：block_shapes 等硬件细节集中在此，上层不感知
  - 计算精度可见：acc_type 和 out_type 分开声明，不混淆
"""

from __future__ import annotations

from functools import cache
from typing import NamedTuple

from ..core.enums import DType


# ============================================================
# ComputeKey — 固定槽位，3 输入 3 输出 + 精度
#
# 三层精度（用 DType 枚举填写）:
#
#   输入/输出 (in0~in2, out0~out2)
#     从 DType.DUT 或 DType.REAL 选。
#     如 DType.DUT.INT16, DType.REAL.FLOAT32
#
#   ACC (acc)
#     累加器内部格式。从 DType.ACC 选。
#     如 DType.ACC.Q12_22（12 位整数 + 22 位小数）
#     ★ 这是累加器的存储格式，不是计算精度！
#
#   计算精度 (compute)
#     乘加运算的实际精度。从 DType.DUT 或 DType.REAL 选。
#     如 DType.REAL.FLOAT32（FP32 混合精度计算）
#     如 DType.DUT.INT16（定点计算）
#
# 各算子槽位:
#   abs:     in0=x                        out0=y
#   add:     in0=a, in1=b                 out0=c
#   matmul:  in0=A, in1=B                 out0=C         acc, compute
#   linear:  in0=x, in1=weight, in2=bias  out0=y         acc, compute
# ============================================================

class ComputeKey(NamedTuple):
    """COMPUTE 表的 key。固定 3 输入 + 3 输出，None 填空。

    用关键字参数 + DType 枚举:
        ComputeKey(
            op="linear",
            in0=DType.DUT.INT16,    in1=DType.DUT.INT16,   in2=DType.ACC.INT32,
            out0=DType.DUT.INT16,
            acc=DType.ACC.Q12_22,  compute=DType.DUT.INT16,
        )
    """
    op: str
    in0: str | None = None         # 输入 0（DType.DUT / DType.REAL）
    in1: str | None = None         # 输入 1
    in2: str | None = None         # 输入 2
    out0: str | None = None        # 输出 0
    out1: str | None = None        # 输出 1
    out2: str | None = None        # 输出 2
    acc: str | None = None         # 累加器格式（DType.ACC）
    compute: str | None = None     # 计算精度（DType.DUT / DType.REAL）


# ============================================================
# TYPES — Golden C 硬件特定信息
#
# 基础类型信息在 core/dtype.py，
# 这里只存 golden C 特有的：C 命名别名 + block 分型 shape。
# ============================================================

TYPES = {
    "int8": {
        "c_names": ["int8", "INT8", "int8_t", "Int8Data", "Int8"],
        "block_shapes": {"zz": (32, 32), "nn": (32, 64)},
    },
    "int16": {
        "c_names": ["int16", "INT16", "int16_t", "Int16Data", "Int16"],
        "block_shapes": {"zz": (16, 16), "nn": (16, 32)},
    },
    "int32": {
        "c_names": ["int32", "INT32", "int32_t"],
        "block_shapes": {"zz": (8, 8), "nn": (8, 16)},
    },
    "float32": {
        "c_names": ["f32", "Float32", "float32", "fp32", "float"],
        "block_shapes": {"zz": (8, 8), "nn": (8, 8)},
    },
    "float64": {
        "c_names": ["f64", "Float64", "float64", "fp64", "double"],
        "block_shapes": {"zz": (4, 4), "nn": (4, 4)},
    },
}


# ============================================================
# CONVERT — 类型转换
# ============================================================

CONVERT = {
    ("int8",    "float32"): "convert_int8_to_float32",
    ("float32", "int8"):    "convert_float32_to_int8",
    ("int16",   "float32"): "convert_int16_to_float32",
    ("float32", "int16"):   "convert_float32_to_int16",
    ("int32",   "float32"): "convert_int32_to_float32",
    ("float32", "int32"):   "convert_float32_to_int32",
    ("int8",    "int16"):   "convert_int8_to_int16",
    ("int16",   "int32"):   "convert_int16_to_int32",
    ("int32",   "int16"):   "convert_int32_to_int16",
    ("int16",   "int8"):    "convert_int16_to_int8",
}


# ============================================================
# COMPUTE — 计算函数
#
# 用关键字参数填 ComputeKey，不用数位置。
# 未使用的槽位不填（默认 None）。
#
# C 函数内部流程（以 linear 为例）:
#   in0(DUT) × in1(DUT) → compute 精度做乘法 → acc 精度累加
#     → +in2(bias) → ×scale → out0(OUT)
# ============================================================

D = DType.DUT
R = DType.REAL
A = DType.ACC

COMPUTE = {
    # --- abs: 一元 ---
    ComputeKey(op="abs", in0=D.INT16, out0=D.INT16):
        "sp_abs_int16",
    ComputeKey(op="abs", in0=A.INT32, out0=A.INT32):
        "sp_abs_int32",

    # --- add: 二元逐元素 ---
    ComputeKey(op="add", in0=D.INT16, in1=D.INT16, out0=D.INT16):
        "sp_vadd_int16",
    ComputeKey(op="add", in0=A.INT32, in1=A.INT32, out0=A.INT32):
        "sp_vadd_int32",

    # --- mul: 二元逐元素，输出比输入宽 ---
    ComputeKey(op="mul", in0=D.INT16, in1=D.INT16, out0=A.INT32, acc=A.Q12_22, compute=D.INT16):
        "sp_vmul_int16_int16_oint32_acc_q12_22",

    # --- matmul: 二元矩阵乘 ---
    ComputeKey(op="matmul", in0=D.INT16, in1=D.INT16, out0=A.INT32, acc=A.Q12_22, compute=D.INT16):
        "sp_gemm_int16_int16_oint32_acc_q12_22",
    ComputeKey(op="matmul", in0=D.INT16, in1=D.INT16, out0=D.INT16, acc=A.Q12_22, compute=D.INT16):
        "sp_gemm_int16_int16_oint16_acc_q12_22",
    ComputeKey(op="matmul", in0=A.INT32, in1=A.INT32, out0=A.INT32, acc=A.Q24_40, compute=A.INT32):
        "sp_gemm_int32_int32_oint32_acc_q24_40",

    # --- linear: 三元 fused（matmul + bias + scale）---
    ComputeKey(op="linear", in0=D.INT16, in1=D.INT16, in2=A.INT32, out0=D.INT16, acc=A.Q12_22, compute=D.INT16):
        "sp_fused_linear_int16_int16_bint32_oint16_acc_q12_22",
    ComputeKey(op="linear", in0=D.INT16, in1=D.INT16, in2=A.INT32, out0=A.INT32, acc=A.Q12_22, compute=D.INT16):
        "sp_fused_linear_int16_int16_bint32_oint32_acc_q12_22",
    ComputeKey(op="linear", in0=A.INT32, in1=A.INT32, in2=A.INT32, out0=A.INT32, acc=A.Q24_40, compute=A.INT32):
        "sp_fused_linear_int32_int32_bint32_oint32_acc_q24_40",
}

del D, R, A  # 清理临时别名


# ============================================================
# 查询 API（@cache 缓存热路径）
# ============================================================

def get_type_info(dtype_name: str) -> dict | None:
    return TYPES.get(dtype_name)


@cache
def get_block_shape(dtype_name: str, fmt: str) -> tuple:
    """查 (dtype, format) 对应的 block shape。"""
    info = TYPES.get(dtype_name)
    if info is not None:
        return info["block_shapes"].get(fmt, (8, 8))
    return (8, 8)


def get_convert_func(src: str, dst: str) -> str | None:
    return CONVERT.get((src, dst))


def get_compute_info(op: str, in0: str, in1: str = None,
                     out0: str = None, compute: str = None) -> dict | None:
    """查计算函数的完整信息。

    Args:
        op, in0, in1: 必须匹配
        out0: 可选过滤，None = 不过滤
        compute: 可选过滤，None = 不过滤

    Returns:
        {"func": str, "key": ComputeKey} or None
    """
    for key, func_name in COMPUTE.items():
        if key.op != op or key.in0 != in0 or key.in1 != in1:
            continue
        if out0 is not None and key.out0 != out0:
            continue
        if compute is not None and key.compute != compute:
            continue
        return {"func": func_name, "key": key}
    return None


def get_compute_func(op: str, in0: str, in1: str = None,
                     out0: str = None, compute: str = None) -> str | None:
    """查计算函数的 C 函数名。"""
    info = get_compute_info(op, in0, in1, out0=out0, compute=compute)
    return info["func"] if info else None


def list_types() -> list[str]:
    return list(TYPES.keys())


def list_ops() -> list[str]:
    return sorted({k.op for k in COMPUTE})


def list_converts() -> list[tuple[str, str]]:
    return list(CONVERT.keys())
