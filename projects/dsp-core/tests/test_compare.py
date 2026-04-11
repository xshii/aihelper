"""测试跨模式对比。"""

import torch
import pytest
from dsp.core.enums import Mode

pytestmark = pytest.mark.it  # compare 涉及多模块协作


class TestCompare:
    def test_compare_basic(self):
        import dsp
        a = dsp.ops.randn(32, dtype=dsp.core.double)
        b = dsp.ops.randn(32, dtype=dsp.core.double)
        report = dsp.context.compare("correlate", a, b, modes=[Mode.TORCH, Mode.PSEUDO_QUANT])
        assert Mode.TORCH in report.results
        assert Mode.PSEUDO_QUANT in report.results

    def test_compare_str(self):
        import dsp
        a = dsp.ops.randn(16, dtype=dsp.core.double)
        b = dsp.ops.randn(16, dtype=dsp.core.double)
        report = dsp.context.compare("correlate", a, b, modes=[Mode.TORCH, Mode.PSEUDO_QUANT])
        s = str(report)
        assert "compare(correlate)" in s

    def test_assert_close(self):
        """float32 的伪量化不截断精度，所以结果应完全一致。"""
        import dsp
        a = dsp.ops.randn(16, dtype=dsp.core.double)
        b = dsp.ops.randn(16, dtype=dsp.core.double)
        report = dsp.context.compare("correlate", a, b, modes=[Mode.TORCH, Mode.PSEUDO_QUANT])
        report.assert_close(Mode.TORCH, Mode.PSEUDO_QUANT, atol=1e-5)
