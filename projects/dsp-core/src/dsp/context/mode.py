"""运行模式管理：torch / pseudo_quant / golden_c。

用法（无缩进）:
    dsp.context.set_mode("pseudo_quant")
    c = a + b
    dsp.context.set_mode("torch")

用法（context manager）:
    with dsp.context.mode_context("golden_c"):
        c = a + b
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Optional

import torch
from torch.utils._python_dispatch import TorchDispatchMode

from ..core.tensor import DSPTensor


# ============================================================
# 模式状态
# ============================================================

from ..core.enums import Mode

VALID_MODES = tuple(Mode)

_default_mode: str = Mode.TORCH
_thread_local = threading.local()
_active_dispatch_mode: Optional[TorchDispatchMode] = None


def get_current_mode() -> str:
    return getattr(_thread_local, "mode", None) or _default_mode


def set_mode(mode: str):
    """设置全局模式（无缩进 API）。"""
    _validate_mode(mode)
    global _default_mode, _active_dispatch_mode

    if _active_dispatch_mode is not None:
        _active_dispatch_mode.__exit__(None, None, None)
        _active_dispatch_mode = None

    _default_mode = mode

    match mode:
        case Mode.PSEUDO_QUANT:
            _active_dispatch_mode = PseudoQuantMode()
            _active_dispatch_mode.__enter__()
        case Mode.GOLDEN_C:
            _active_dispatch_mode = GoldenCMode()
            _active_dispatch_mode.__enter__()


@contextmanager
def mode_context(mode: str):
    """临时切换模式的 context manager。"""
    _validate_mode(mode)
    old = getattr(_thread_local, "mode", None)
    _thread_local.mode = mode

    dispatch = None
    match mode:
        case Mode.PSEUDO_QUANT:
            dispatch = PseudoQuantMode()
            dispatch.__enter__()
        case Mode.GOLDEN_C:
            dispatch = GoldenCMode()
            dispatch.__enter__()

    try:
        yield
    finally:
        if dispatch is not None:
            dispatch.__exit__(None, None, None)
        _thread_local.mode = old


def _validate_mode(mode: str):
    if mode not in VALID_MODES:
        raise ValueError(f"未知模式 '{mode}'。可用: {VALID_MODES}")


# ============================================================
# PseudoQuantMode
# ============================================================

class PseudoQuantMode(TorchDispatchMode):
    """伪量化 dispatch mode。拦截 aten op，输入输出加 fake_quantize。"""

    def __init__(self, codec_getter=None):
        super().__init__()
        if codec_getter is None:
            from ..core.dtype import get_codec
            codec_getter = get_codec
        self._codec_getter = codec_getter

    def __torch_dispatch__(self, func, types, args=(), kwargs=None):
        kwargs = kwargs or {}
        new_args = _tree_map_tensors(args, self._fake_quantize)
        result = func(*new_args, **kwargs)
        result = _map_result(result, self._fake_quantize)
        return result

    def _fake_quantize(self, t: torch.Tensor) -> torch.Tensor:
        if isinstance(t, DSPTensor) and t._dsp_dtype is not None:
            try:
                codec = self._codec_getter(t._dsp_dtype)
                q = codec.fake_quantize(t, t._dsp_dtype)
                if not isinstance(q, DSPTensor):
                    q = DSPTensor.create(q, t._dsp_dtype)
                return q
            except (TypeError, NotImplementedError):
                pass
        return t


# ============================================================
# GoldenCMode
# ============================================================

class _GoldenAtenRegistry:
    _store: dict[str, callable] = {}

    @classmethod
    def register(cls, name: str, func: callable):
        cls._store[name] = func

    @classmethod
    def get(cls, name: str) -> Optional[callable]:
        return cls._store.get(name)


def register_golden_aten(aten_op_name: str):
    """注册标准 aten op 的 golden C 实现。"""
    def decorator(func):
        _GoldenAtenRegistry.register(aten_op_name, func)
        return func
    return decorator


class GoldenCMode(TorchDispatchMode):
    """Golden C dispatch mode。已注册的 aten op 不允许降级。"""

    def __torch_dispatch__(self, func, types, args=(), kwargs=None):
        kwargs = kwargs or {}

        op_name = str(func.name()) if hasattr(func, 'name') else str(func)
        golden_impl = _GoldenAtenRegistry.get(op_name)

        if golden_impl is not None:
            result = golden_impl(*args, **kwargs)
            if result is None:
                from ..core.errors import GoldenNotAvailable
                raise GoldenNotAvailable(
                    f"golden_c: {op_name} 已注册但返回 None。"
                )
            return result

        return func(*args, **kwargs)


# ============================================================
# 辅助函数
# ============================================================

def _tree_map_tensors(args, fn):
    result = []
    for a in args:
        if isinstance(a, torch.Tensor):
            result.append(fn(a))
        elif isinstance(a, (list, tuple)):
            result.append(type(a)(_tree_map_tensors(a, fn)))
        else:
            result.append(a)
    return tuple(result)


def _map_result(result, fn):
    if isinstance(result, torch.Tensor):
        return fn(result)
    if isinstance(result, (list, tuple)):
        return type(result)(_map_result(r, fn) for r in result)
    return result
