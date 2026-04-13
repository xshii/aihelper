"""Golden C 声明表 — CONVERT + COMPUTE 注册表。

两张��:
  CONVERT  — 类型转换函数：(src, dst) → C 函数名
  COMPUTE  — 计算函数：ComputeKey → C 函数名

block 类型信息（BlockShape, TypeInfo, BLOCK_TYPES）在 core/block.py。
"""

from __future__ import annotations

from typing import NamedTuple

from ..core.block import get_block_shape as get_block_shape  # noqa: F401  re-export
from ..core.block import BlockShape as BlockShape, TypeInfo as TypeInfo, BLOCK_TYPES as BLOCK_TYPES  # noqa: F401


# ============================================================
# ComputeKey
# ============================================================

class ComputeKey(NamedTuple):
    """COMPUTE 表的 key。

    None 字段在匹配时当 wildcard（任意）。

    用法:
        ComputeKey(op="linear", src0="bf16", dst0="bf16")
    """
    op: str
    src0: str | None = None
    src1: str | None = None
    src2: str | None = None
    dst0: str | None = None
    dst1: str | None = None
    dst2: str | None = None
    compute_dtype: str | None = None


# ============================================================
# CONVERT — 类型转换
# ============================================================

CONVERT = {}  # auto_register 自动填充


# ============================================================
# COMPUTE — 计算函数
# ============================================================

COMPUTE = {}  # auto_register 自动填充

_COMPUTE_BY_OP: dict[str, list] = {}
for _key, _func in COMPUTE.items():
    _COMPUTE_BY_OP.setdefault(_key.op, []).append((_key, _func))


# ============================================================
# 查询 API
# ============================================================

def get_type_info(dtype_name: str) -> TypeInfo | None:
    return BLOCK_TYPES.get(dtype_name)


def require_convert_func(src: str, dst: str) -> str:
    """查转换函数，找不到直接 raise。"""
    func = CONVERT.get((src, dst))
    if func is not None:
        return func
    existing = [f"  {s} → {d}" for s, d in CONVERT]
    hint = "\n".join(existing) if existing else "  （无）"
    from ..core.errors import ManifestNotFound
    raise ManifestNotFound(
        f"convert({src} → {dst}) 未在 CONVERT 表中注册。\n"
        f"已注册的转换:\n{hint}"
    )


def get_compute_info(query: ComputeKey) -> dict | None:
    """用 ComputeKey 查计算函数。

    匹配规则: query 或 key 任一方为 None 的字段不参与过滤。
    匹配到 0 个 → 返回 None。匹配到多个 → raise 歧义错误。
    """
    match_fields = tuple(f for f in ComputeKey._fields if f != "op")
    matches = []
    for key, func_name in _COMPUTE_BY_OP.get(query.op, []):
        if all(
            getattr(query, f) is None or getattr(key, f) is None
            or getattr(query, f) == getattr(key, f)
            for f in match_fields
        ):
            matches.append({"func": func_name, "key": key})

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        from ..core.errors import ManifestNotFound
        keys_str = "\n".join(f"  {m['key']}" for m in matches)
        raise ManifestNotFound(
            f"compute({query.op}) 匹配到多个结果（歧义）:\n{keys_str}\n"
            f"查询: {query}"
        )
    return None


def require_compute_info(query: ComputeKey) -> dict:
    """查计算函数，找不到直接 raise。"""
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
        f"该 op 已注册的组合:\n{hint}"
    )


def get_compute_func(query: ComputeKey) -> str | None:
    info = get_compute_info(query)
    return info["func"] if info else None


def list_types() -> list[str]:
    return list(BLOCK_TYPES.keys())


def list_ops() -> list[str]:
    return sorted({k.op for k in COMPUTE})


def list_converts() -> list[tuple[str, str]]:
    return list(CONVERT.keys())
