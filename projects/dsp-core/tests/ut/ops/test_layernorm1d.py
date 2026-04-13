"""ops/layernorm1d 基础单元测试。"""

import pytest
import dsp
from dsp.core.enums import Mode
from dsp.golden.call import is_available


class TestLayerNorm1dTorch:
    def test_basic(self):
        x = dsp.data.randn(8, dtype=dsp.core.bf16)
        g = dsp.data.ones(8, dtype=dsp.core.bf16)
        b = dsp.data.zeros(8, dtype=dsp.core.bf16)
        out = dsp.ops.layernorm1d(x, g, b)
        assert list(out.shape) == [8]


@pytest.mark.skipif(not is_available(), reason="golden C not available")
class TestLayerNorm1dGoldenC:
    def setup_method(self):
        dsp.context.set_mode(Mode.GOLDEN_C)

    def teardown_method(self):
        dsp.context.set_mode(Mode.TORCH)

    def test_basic(self):
        x = dsp.data.randn(8, dtype=dsp.core.bf16)
        g = dsp.data.ones(8, dtype=dsp.core.bf16)
        b = dsp.data.zeros(8, dtype=dsp.core.bf16)
        out = dsp.ops.layernorm1d(x, g, b)
        assert list(out.shape) == [8]
