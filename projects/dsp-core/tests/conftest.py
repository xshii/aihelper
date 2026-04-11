"""pytest 配置 + 共享 fixtures。

测试分三级:
    @pytest.mark.ut  — 单元测试：单函数/单类，无 I/O
    @pytest.mark.it  — 集成测试：多模块协作，可有临时文件
    @pytest.mark.st  — 系统测试：完整端到端流程

运行方式:
    pytest                    — 全部
    pytest -m ut              — 只跑单元测试
    pytest -m "not st"        — 跳过系统测试（快速验证）
    pytest -m st              — 只跑端到端

Fixtures（弱 AI 直接用，不需要自己造数据）:
    int16_pair     — 一对 int16 DSPTensor (64,)
    float32_pair   — 一对 float32 DSPTensor (64,)
    int16_matrix   — int16 矩阵 (4, 8)
    tmp_output_dir — 临时输出目录（自动清理）
    sample_pipe    — 预建的 DataPipe 实例
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
import torch
import tempfile
import shutil


# ============================================================
# 数据 Fixtures
# ============================================================

@pytest.fixture
def int16_pair():
    """一对 INT16 DSPTensor (64,)。"""
    import dsp
    a = dsp.ops.randn(64, dtype=dsp.core.bint16)
    b = dsp.ops.randn(64, dtype=dsp.core.bint16)
    return a, b


@pytest.fixture
def float32_pair():
    """一对 Float32 DSPTensor (64,)。"""
    import dsp
    a = dsp.ops.randn(64, dtype=dsp.core.double)
    b = dsp.ops.randn(64, dtype=dsp.core.double)
    return a, b


@pytest.fixture
def int16_matrix():
    """INT16 矩阵 (4, 8)。"""
    import dsp
    return dsp.ops.randn(4, 8, dtype=dsp.core.bint16)


@pytest.fixture
def float32_matrix():
    """Float32 矩阵 (4, 8)。"""
    import dsp
    return dsp.ops.randn(4, 8, dtype=dsp.core.double)


# ============================================================
# 目录 Fixtures
# ============================================================

@pytest.fixture
def tmp_output_dir():
    """临时输出目录（测试结束自动清理）。"""
    d = tempfile.mkdtemp(prefix="dsp_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ============================================================
# DataPipe Fixtures
# ============================================================

@pytest.fixture
def sample_pipe():
    """预建的 float32 DataPipe (4, 8)。"""
    from dsp.data.pipe import DataPipe
    t = torch.randn(4, 8)
    return DataPipe(t, dtype="float32")


# ============================================================
# 模式还原（防止测试间污染）
# ============================================================

@pytest.fixture(autouse=True)
def reset_state():
    """每个测试后还原为 torch 模式 + 关闭 runloop。"""
    yield
    import dsp
    from dsp.core.enums import Mode
    from dsp.context import runloop
    try:
        dsp.context.set_mode(Mode.TORCH)
    except Exception:
        pass
    # 重置 runloop 全局状态，防止测试间污染
    runloop._state = runloop.RunState()
