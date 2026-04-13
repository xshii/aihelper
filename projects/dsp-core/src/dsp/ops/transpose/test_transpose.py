"""ops/transpose 基础单元测试。"""

import dsp


class TestTranspose:
    def test_2d(self):
        x = dsp.data.randn(3, 5, dtype=dsp.core.bf16)
        t = dsp.ops.transpose(x)
        assert list(t.shape) == [5, 3]

    def test_3d_last_two(self):
        x = dsp.data.randn(2, 3, 4, dtype=dsp.core.bf16)
        t = dsp.ops.transpose(x)
        assert list(t.shape) == [2, 4, 3]

    def test_custom_dims(self):
        x = dsp.data.randn(2, 3, 4, dtype=dsp.core.bf16)
        t = dsp.ops.transpose(x, 0, 2)
        assert list(t.shape) == [4, 3, 2]
