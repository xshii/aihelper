"""系统测试：完整端到端验证流程。"""

import os
import json
import pytest
import torch
from dsp.core.enums import Mode, RunMode
from dsp.data.datagen import USE_INPUT_MODES

pytestmark = pytest.mark.st


class TestGenerateInput:
    def test_generate_creates_files(self, tmp_output_dir):
        """generate_input 应为每种策略创建数据目录。"""
        import dsp
        dsp.context.set_global_runmode(RunMode.GENERATE_INPUT, tmp_output_dir, seed=42)
        rounds = 0
        while not dsp.context.is_global_done():
            x = dsp.ops.randn(4, 8, dtype=dsp.core.int16)
            w = dsp.ops.randn(8, 4, dtype=dsp.core.int16)
            b = dsp.ops.randn(1, 4, dtype=dsp.core.int16)
            result = dsp.ops.linear(x, w, b)
            dsp.context.submit_output(result)
            rounds += 1
        dsp.context.export()

        assert rounds == 8  # 8 种策略（含 math）

        # 找到用例目录
        case_dirs = [d for d in os.listdir(tmp_output_dir)
                     if os.path.isdir(os.path.join(tmp_output_dir, d))]
        assert len(case_dirs) == 1
        case_dir = os.path.join(tmp_output_dir, case_dirs[0])

        # 检查日志
        log = json.loads(open(os.path.join(case_dir, "run_log.json")).read())
        assert log["seed"] == 42
        assert len(log["rounds"]) == 8

        # 检查策略目录有数据
        assert os.path.isdir(os.path.join(case_dir, "precision_exact"))
        assert os.path.isdir(os.path.join(case_dir, "random"))
        txt_files = [f for f in os.listdir(os.path.join(case_dir, "precision_exact"))
                     if f.endswith(".txt")]
        assert len(txt_files) > 0


class TestSeedReproducibility:
    def test_same_seed_same_data(self, tmp_output_dir):
        """相同 seed 应产生完全相同的数据。"""
        import dsp

        def run_once(seed, subdir):
            path = os.path.join(tmp_output_dir, subdir)
            os.makedirs(path, exist_ok=True)
            dsp.context.set_global_runmode(RunMode.GENERATE_INPUT, path, seed=seed)
            results = []
            while not dsp.context.is_global_done():
                x = dsp.ops.randn(4, 8, dtype=dsp.core.float32)
                result = x.sum().item()
                results.append(result)
                dsp.context.submit_output(x)
            return results

        r1 = run_once(seed=12345, subdir="run1")
        r2 = run_once(seed=12345, subdir="run2")
        assert r1 == r2


class TestUseInput:
    def test_use_input_loads_and_compares(self, tmp_output_dir):
        """generate_input → use_input 完整流程。"""
        import dsp

        # pseudo_quant only（torch 已在 generate_input 跑过）
        original_modes = list(USE_INPUT_MODES)
        USE_INPUT_MODES[:] = [Mode.PSEUDO_QUANT]

        try:
            # generate_input
            dsp.context.set_global_runmode(RunMode.GENERATE_INPUT, tmp_output_dir, seed=99)
            while not dsp.context.is_global_done():
                x = dsp.ops.randn(4, 8, dtype=dsp.core.int16)
                w = dsp.ops.randn(8, 4, dtype=dsp.core.int16)
                b = dsp.ops.randn(1, 4, dtype=dsp.core.int16)
                result = dsp.ops.linear(x, w, b)
                dsp.context.submit_output(result)
            dsp.context.export()

            # use_input
            dsp.context.set_global_runmode(RunMode.USE_INPUT, tmp_output_dir, seed=99)
            rounds = 0
            while not dsp.context.is_global_done():
                x = dsp.ops.randn(4, 8, dtype=dsp.core.int16)
                w = dsp.ops.randn(8, 4, dtype=dsp.core.int16)
                b = dsp.ops.randn(1, 4, dtype=dsp.core.int16)
                result = dsp.ops.linear(x, w, b)
                dsp.context.submit_output(result)
                rounds += 1
            dsp.context.export()

            assert rounds == 8 * 1  # 8 策略 × 1 模式（pseudo_quant only）

            # 检查日志存在
            case_dirs = [d for d in os.listdir(tmp_output_dir)
                         if os.path.isdir(os.path.join(tmp_output_dir, d))]
            case_dir = os.path.join(tmp_output_dir, case_dirs[0])
            log = json.loads(open(os.path.join(case_dir, "run_log.json")).read())
            assert log["seed"] == 99
            assert len(log["rounds"]) == 8  # 8 策略 × 1 模式
        finally:
            USE_INPUT_MODES[:] = original_modes
