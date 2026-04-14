"""Golden C 调用层 — manifest 查表 + C 函数调用。

对外:
    convert(data_np, src_type, dst_type) → np.ndarray
    compute(op, a_np, b_np, type_a, type_b) → np.ndarray
    is_available() → bool

所有函数操作 numpy flat array，不碰 torch / 文件 / block 格式。
block 格式是上层（data 模块）的事。
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from .manifest import require_convert_func, require_compute_info, ComputeKey
from ..core.errors import GoldenNotAvailable

logger = logging.getLogger("dsp.golden")


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
        data: flat double numpy array
        src_type: 源类型名（如 "bf16"）
        dst_type: 目标类型名（如 "double"）

    Returns:
        flat double numpy array
    """
    func_name = require_convert_func(src_type, dst_type)
    lib = _get_lib()
    func = getattr(lib, func_name, None)
    if func is None:
        raise GoldenNotAvailable(
            f"C 函数 '{func_name}' 在 .so 中不存在。"
        )
    dst = np.empty_like(data)
    func(data.astype(np.double), dst, data.size)
    return dst


def compute(*inputs: np.ndarray, query: ComputeKey,
            op_params: Optional[dict] = None) -> dict:
    """计算。

    Args:
        *inputs: flat double numpy arrays（个数由算子决定）
        query: ComputeKey 查询条件（部分填写，None 字段不过滤）
        op_params: op 非 tensor 参数（如 transpose 的 dim0/dim1），透传到
            OpConvention.call_c_func 的 **params

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
    from ..core.convention import require_convention
    conv = require_convention(op)

    inputs: list[np.ndarray] = [inp.astype(np.double) for inp in inputs]  # double
    key = info["key"]
    op_params = op_params or {}
    out_np = conv.call_c_func(func, *inputs, compute_key=key, **op_params)
    return {
        "result": out_np,
        "key": key,
    }


# ============================================================
# 内部
# ============================================================

_lib_cache = None

def _auto_build() -> bool:
    """JIT 编译 _raw_bindings.so。不依赖 Makefile，直接调 cmake。

    pip install 后也能用：只要系统有 cmake 和 C++ 编译器，
    pybind11 从当前 Python 环境自动找。
    """
    import subprocess
    import sys
    import logging
    from pathlib import Path
    from ..config import GOLDEN_BUILD_DIR

    logger = logging.getLogger("dsp.golden")

    # 定位关键路径（相对于本文件，pip install 后也能找到）
    golden_dir = Path(__file__).resolve().parent          # src/dsp/golden/
    cmake_source = golden_dir                              # CMakeLists.txt 所在目录
    build_dir = GOLDEN_BUILD_DIR                           # src/dsp/golden/build/

    if not (cmake_source / "CMakeLists.txt").exists():
        logger.warning("自动编译跳过: CMakeLists.txt 不存在 (%s)", cmake_source)
        return False

    build_dir.mkdir(parents=True, exist_ok=True)
    python_exe = sys.executable

    # pybind11 cmake dir
    try:
        import pybind11
        pybind11_dir = pybind11.get_cmake_dir()
    except ImportError:
        logger.warning("自动编译跳过: pybind11 未安装 (pip install pybind11)")
        return False

    logger.info("JIT 编译 _raw_bindings... (build_dir=%s)", build_dir)

    def _run(cmd):
        r = subprocess.run(cmd, cwd=str(build_dir), capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            logger.warning("命令失败: %s\n%s", " ".join(cmd), r.stderr[-500:] if r.stderr else "")
        return r.returncode == 0

    # cmake configure
    ok = _run([
        "cmake", str(cmake_source),
        f"-Dpybind11_DIR={pybind11_dir}",
        f"-DPYTHON_EXECUTABLE={python_exe}",
        "-Wno-dev",
    ])
    if not ok:
        return False

    # cmake build
    ok = _run(["cmake", "--build", "."])
    if ok:
        logger.info("JIT 编译成功")
    return ok


def _get_lib():
    """加载 C++ 绑定模块。找不到时自动触发一次编译。

    加载策略（绕开 sys.path + ABI tag 匹配的陷阱）:
      1. 优先找当前 Python ABI tag 的 .so（sysconfig.EXT_SUFFIX）
      2. 其次找任意 _raw_bindings*.so（可能是别的 Python 编的，会报清晰错误）
      3. 用 importlib.util.spec_from_file_location 按绝对路径加载
    """
    global _lib_cache
    if _lib_cache is not None:
        return _lib_cache

    from ..config import GOLDEN_BUILD_DIR

    for attempt in range(2):
        mod = _load_by_path(GOLDEN_BUILD_DIR)
        if mod is not None:
            _lib_cache = mod
            return _lib_cache
        if attempt == 0 and _auto_build():
            continue
        raise ImportError(
            "golden: 未找到 _raw_bindings。自动编译失败或 .so 与当前 Python ABI 不匹配。\n"
            f"当前 Python: EXT_SUFFIX={_ext_suffix()}\n"
            f"build_dir:   {GOLDEN_BUILD_DIR}\n"
            "手动修复: 删掉 build 目录重新 make build-golden（确认用同一个 Python）。"
        )


def _ext_suffix() -> str:
    import sysconfig
    return sysconfig.get_config_var("EXT_SUFFIX") or ".so"


def _load_by_path(build_dir):
    """扫 build_dir 里的 _raw_bindings*.so，按路径加载。找不到/不匹配返回 None。"""
    import importlib.util
    from pathlib import Path

    build_dir = Path(build_dir)
    if not build_dir.exists():
        return None

    # 1) 优先匹配当前 Python ABI
    exact = build_dir / f"_raw_bindings{_ext_suffix()}"
    candidates = [exact] if exact.exists() else sorted(build_dir.glob("_raw_bindings*.so"))
    if not candidates:
        return None

    for so_path in candidates:
        try:
            spec = importlib.util.spec_from_file_location("_raw_bindings", so_path)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
        except ImportError as e:
            logger.warning("加载 %s 失败（可能是 ABI 不匹配）: %s", so_path.name, e)
            continue
    return None
