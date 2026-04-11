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

from ..core.dtype import DType


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
#   abs:     src0=x                        dst0=y
#   add:     src0=a, src1=b                 dst0=c
#   matmul:  src0=A, src1=B                 dst0=C         acc, compute
#   linear:  src0=x, src1=weight, src2=bias  dst0=y         acc, compute
# ============================================================

class ComputeKey(NamedTuple):
    """COMPUTE 表的 key。固定 3 输入 + 3 输出，None 填空。

    命名与硬件 C 接口一致: src = 输入, dst = 输出。

    用关键字参数 + DType 枚举:
        ComputeKey(
            op="linear",
            src0=DType.DUT.INT16,   src1=DType.DUT.INT16,   src2=DType.DUT.INT32,
            dst0=DType.DUT.INT16,
            acc=DType.ACC.Q12_22,   compute_dtype=DType.DUT.INT16,
        )
    """
    op: str
    src0: str | None = None         # 输入 0（DType.DUT / DType.REAL）
    src1: str | None = None         # 输入 1
    src2: str | None = None         # 输入 2
    dst0: str | None = None         # 输出 0
    dst1: str | None = None         # 输出 1
    dst2: str | None = None         # 输出 2
    acc: str | None = None          # 累加器格式（DType.ACC）
    compute_dtype: str | None = None # 计算精度（DType.DUT / DType.REAL）


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

CONVERT = {}  # auto_register 自动填充


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

COMPUTE = {}  # auto_register 自动填充

# 按 op 分组索引（避免每次查询遍历整个 COMPUTE 表）
_COMPUTE_BY_OP: dict[str, list] = {}
for _key, _func in COMPUTE.items():
    _COMPUTE_BY_OP.setdefault(_key.op, []).append((_key, _func))


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


def require_convert_func(src: str, dst: str) -> str:
    """查转换函数，找不到直接 raise 并给出诊断信息。"""
    func = CONVERT.get((src, dst))
    if func is not None:
        return func
    existing = [f"  {s} → {d}" for s, d in CONVERT]
    hint = "\n".join(existing) if existing else "  （无）"
    from ..core.errors import ManifestNotFound
    raise ManifestNotFound(
        f"convert({src} → {dst}) 未在 CONVERT 表中注册。\n"
        f"已注册的转换:\n{hint}\n"
        f"修复: 在 manifest.py CONVERT 表中添加 (\"{src}\", \"{dst}\"): \"convert_{src}_to_{dst}\"。"
    )


_MATCH_FIELDS = ("src0", "src1", "src2", "dst0", "dst1", "dst2", "acc", "compute_dtype")


def get_compute_info(query: ComputeKey) -> dict | None:
    """用 ComputeKey 查计算函数。query 中 None 字段不过滤。

    Returns:
        {"func": str, "key": ComputeKey} or None
    """
    for key, func_name in _COMPUTE_BY_OP.get(query.op, []):
        if all(
            getattr(query, f) is None or getattr(query, f) == getattr(key, f)
            for f in _MATCH_FIELDS
        ):
            return {"func": func_name, "key": key}
    return None


def require_compute_info(query: ComputeKey) -> dict:
    """查计算函数，找不到直接 raise 并给出诊断信息。"""
    info = get_compute_info(query)
    if info is not None:
        return info
    existing = [
        f"  ({k.src0}, {k.src1}) → dst0={k.dst0}"
        for k, _ in _COMPUTE_BY_OP.get(query.op, [])
    ]
    hint = "\n".join(existing) if existing else "  （无）"
    from ..core.errors import ManifestNotFound
    raise ManifestNotFound(
        f"compute({query.op}, src0={query.src0}, src1={query.src1}, dst0={query.dst0}) 未匹配。\n"
        f"该 op 已注册的组合:\n{hint}\n"
        f"修复: 在 manifest.py COMPUTE 表或 @register_op(golden_c={{...}}) 中添加 ComputeKey。"
    )


def get_compute_func(query: ComputeKey) -> str | None:
    """查计算函数的 C 函数名。"""
    info = get_compute_info(query)
    return info["func"] if info else None


def list_types() -> list[str]:
    return list(TYPES.keys())


def list_ops() -> list[str]:
    return sorted({k.op for k in COMPUTE})


def list_converts() -> list[tuple[str, str]]:
    return list(CONVERT.keys())
