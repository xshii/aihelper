"""Golden C 调用层 — manifest 查表 + C 函数调用。

对外:
    convert(data_np, src_type, dst_type) → np.ndarray
    compute(op, a_np, b_np, type_a, type_b) → np.ndarray
    is_available() → bool

所有函数操作 numpy flat array，不碰 torch / 文件 / block 格式。
block 格式是上层（data 模块）的事。
"""

from __future__ import annotations

import numpy as np

from .manifest import require_convert_func, require_compute_info, ComputeKey
from ..core.errors import GoldenNotAvailable


def is_available() -> bool:
    """C++ 绑定是否可用。

    返回 False 时说明 _raw_bindings.so 未编译。
    修复: make build-golden（需要先 pip install pybind11）。
    如果编译后仍不可用，检查 src/dsp/golden/build/ 下是否有 _raw_bindings*.so 文件。
    """
    try:
        _get_lib()
        return True
    except ImportError:
        return False


def convert(data: np.ndarray, src_type: str, dst_type: str) -> np.ndarray:
    """类型转换。

    Args:
        data: flat float32 numpy array（原始字节）
        src_type: 源类型名（如 "int16"）
        dst_type: 目标类型名（如 "float32"）

    Returns:
        flat float32 numpy array
    """
    func_name = require_convert_func(src_type, dst_type)
    lib = _get_lib()
    func = getattr(lib, func_name, None)
    if func is None:
        raise GoldenNotAvailable(
            f"C 函数 '{func_name}' 在 .so 中不存在。"
        )
    dst = np.empty_like(data)
    func(data.astype(np.float32), dst, data.size)
    return dst


def compute(*inputs: np.ndarray, query: ComputeKey) -> dict:
    """计算。

    Args:
        *inputs: flat float32 numpy arrays（个数由算子决定）
        query: ComputeKey 查询条件（部分填写，None 字段不过滤）

    Returns:
        {"result": np.ndarray, "key": ComputeKey}
    """
    info = require_compute_info(query)
    op = query.op
    func_name = info["func"]
    lib = _get_lib()
    func = getattr(lib, func_name, None)
    if func is None:
        raise GoldenNotAvailable(
            f"C 函数 '{func_name}' 在 .so 中不存在。"
        )
    from .op_convention import require_convention
    conv = require_convention(op)

    inputs_f32 = [inp.astype(np.float32) for inp in inputs]
    key = info["key"]
    out_np = conv.call_c_func(func, *inputs_f32, compute_key=key)
    return {
        "result": out_np,
        "key": key,
    }


# ============================================================
# 内部
# ============================================================

_lib_cache = None

def _get_lib():
    """加载 C++ 绑定模块（make build-golden 编译产物在 build/ 目录）。"""
    global _lib_cache
    if _lib_cache is not None:
        return _lib_cache

    import sys
    from ..config import GOLDEN_BUILD_DIR
    build_dir = str(GOLDEN_BUILD_DIR)
    if GOLDEN_BUILD_DIR.exists() and build_dir not in sys.path:
        sys.path.insert(0, build_dir)
    try:
        import _raw_bindings
        _lib_cache = _raw_bindings
        return _lib_cache
    except ImportError:
        raise ImportError(
            "golden: 未找到 _raw_bindings。请运行 make build-golden 编译 C++ 绑定。"
        )
