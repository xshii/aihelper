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

from .manifest import get_convert_func, get_compute_info
from ..core.errors import GoldenNotAvailable, ManifestNotFound, ConventionNotFound


def is_available() -> bool:
    """C++ 绑定是否可用。"""
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
    func_name = get_convert_func(src_type, dst_type)
    if func_name is None:
        raise ManifestNotFound(
            f"convert({src_type} → {dst_type}) 未在 CONVERT 表中注册。"
        )
    lib = _get_lib()
    func = getattr(lib, func_name, None)
    if func is None:
        raise GoldenNotAvailable(
            f"C 函数 '{func_name}' 在 .so 中不存在。"
        )
    dst = np.empty_like(data)
    func(data.astype(np.float32), dst, data.size)
    return dst


def compute(op: str, *inputs: np.ndarray,
            type_a: str, type_b: str = None,
            out0: str = None, compute: str = None) -> dict:
    """计算。

    Args:
        op: 操作名
        *inputs: flat float32 numpy arrays（个数由算子决定）
        type_a, type_b: 前两个输入的类型名
        out0: 输出类型过滤
        compute: 计算精度过滤

    Returns:
        {"result": np.ndarray, "key": ComputeKey}
    """
    info = get_compute_info(op, type_a, type_b, out0=out0, compute=compute)
    if info is None:
        raise ManifestNotFound(
            f"compute({op}, {type_a}, {type_b}) 未在 COMPUTE 表中注册。"
        )
    func_name = info["func"]
    lib = _get_lib()
    func = getattr(lib, func_name, None)
    if func is None:
        raise GoldenNotAvailable(
            f"C 函数 '{func_name}' 在 .so 中不存在。"
        )
    from .op_convention import get_convention
    conv = get_convention(op)
    if conv is None:
        raise ConventionNotFound(f"算子 '{op}' 无 OpConvention。")

    inputs_f32 = [inp.astype(np.float32) for inp in inputs]
    out_np = conv.call_c_func(func, *inputs_f32)
    return {
        "result": out_np,
        "key": info["key"],
    }


# ============================================================
# 内部
# ============================================================

_lib_cache = None

def _get_lib():
    """懒加载 C++ 绑定模块。

    加载顺序:
      1. sys.path 上的 _raw_bindings（用户自行安装的真 .so）
      2. golden_c/build/ 下的编译产物
      3. fake_so（纯 Python 模拟，开发/测试用）
    """
    global _lib_cache
    if _lib_cache is not None:
        return _lib_cache

    # 1. sys.path 上直接 import
    try:
        import _raw_bindings
        _lib_cache = _raw_bindings
        return _lib_cache
    except ImportError:
        pass

    # 2. src/dsp/golden/build/ 目录（bindings.cpp 编译产物）
    import sys
    from pathlib import Path
    build_dir = Path(__file__).resolve().parent / "build"
    if build_dir.exists() and str(build_dir) not in sys.path:
        sys.path.insert(0, str(build_dir))
        try:
            import _raw_bindings
            _lib_cache = _raw_bindings
            return _lib_cache
        except ImportError:
            pass

    # 3. fake_so（纯 Python 模拟）
    try:
        from . import fake_so
        _lib_cache = fake_so
        return _lib_cache
    except ImportError:
        pass

    raise ImportError("golden: 未找到 _raw_bindings 或 fake_so")
