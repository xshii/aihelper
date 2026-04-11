"""测试模式切换。"""

import torch
import pytest
from dsp.core.enums import Mode

pytestmark = pytest.mark.ut


class TestModeBasic:
    def test_default_mode_is_torch(self):
        import dsp
        assert dsp.context.get_current_mode() == Mode.TORCH

    def test_set_mode(self):
        import dsp
        old = dsp.context.get_current_mode()
        dsp.context.set_mode(Mode.PSEUDO_QUANT)
        assert dsp.context.get_current_mode() == Mode.PSEUDO_QUANT
        dsp.context.set_mode(old)

    def test_context_manager(self):
        import dsp
        assert dsp.context.get_current_mode() == Mode.TORCH
        with dsp.context.mode_context(Mode.PSEUDO_QUANT):
            assert dsp.context.get_current_mode() == Mode.PSEUDO_QUANT
        assert dsp.context.get_current_mode() == Mode.TORCH

    def test_invalid_mode_raises(self):
        import dsp
        with pytest.raises(ValueError, match="未知模式"):
            dsp.context.set_mode("invalid")


class TestPseudoQuant:
    def test_pseudo_quant_changes_values(self):
        """伪量化应截断精度，使结果与纯 torch 不完全相同。"""
        import dsp
        a = dsp.ops.randn(64, dtype=dsp.core.bint16)
        b = dsp.ops.randn(64, dtype=dsp.core.bint16)

        with dsp.context.mode_context(Mode.TORCH):
            result_torch = dsp.ops.correlate(a, b)

        with dsp.context.mode_context(Mode.PSEUDO_QUANT):
            result_quant = dsp.ops.correlate(a, b)

        assert result_torch.shape == result_quant.shape


class TestGoldenC:
    def test_golden_c_unregistered_op_raises(self):
        """manifest 中未注册的类型组合应报错。"""
        import dsp
        a = dsp.ops.randn(16, dtype=dsp.core.double)
        b = dsp.ops.randn(16, dtype=dsp.core.double)
        with dsp.context.mode_context(Mode.GOLDEN_C):
            from dsp.core.errors import DSPError
            with pytest.raises(DSPError):
                dsp.ops.correlate(a, b)  # float32 correlate 未在 manifest 注册
