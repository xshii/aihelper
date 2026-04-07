"""测试自定义算子。"""

import torch
import pytest

pytestmark = pytest.mark.ut


class TestCorrelate:
    def test_float_correlate(self, float32_pair):
        import dsp
        a, b = float32_pair
        c = dsp.ops.correlate(a, b)
        assert isinstance(c, dsp.core.DSPTensor)
        # 互相关输出长度 = len(a) + len(b) - 1
        assert c.shape[-1] == a.shape[-1] + b.shape[-1] - 1

    def test_complex_correlate(self, iq16_pair):
        import dsp
        a, b = iq16_pair
        c = dsp.ops.correlate(a, b)
        assert c.is_complex()
        assert c.shape[-1] == a.shape[-1] + b.shape[-1] - 1

    def test_autocorrelation(self):
        """自相关: correlate(a, a) 的零延迟 = 能量。"""
        import dsp
        a = dsp.ops.tensor([1.0, 2.0, 3.0], dtype=dsp.core.float32)
        c = dsp.ops.correlate(a, a)
        # 零延迟（中心点）应等于 sum(a^2) = 14
        center = c.shape[-1] // 2
        assert abs(c[center].item() - 14.0) < 1e-5


class TestOpRegistry:
    def test_list_ops(self):
        import dsp
        ops = dsp.ops.list_ops()
        assert "correlate" in ops

    def test_unknown_op_raises(self):
        import dsp
        a = dsp.ops.randn(10, dtype=dsp.core.float32)
        from dsp.core.errors import OpNotRegistered
        with pytest.raises(OpNotRegistered):
            dsp.ops.dispatch("nonexistent_op", a, a)

    def test_register_custom_op(self):
        import dsp

        @dsp.ops.register_op
        def my_custom_add(a, b):
            return a + b

        a = dsp.ops.randn(10, dtype=dsp.core.float32)
        result = dsp.ops.dispatch("my_custom_add", a, a)
        assert result.shape == a.shape
