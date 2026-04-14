"""ops/transpose 基础单元测试。"""

import dsp
from dsp.core.enums import Mode


class TestTranspose:
    def test_2d(self):
        x = dsp.data.randn(3, 5, dtype=dsp.core.bf16)
        t = dsp.ops.transpose(x, -2, -1)
        assert list(t.shape) == [5, 3]

    def test_3d_last_two(self):
        x = dsp.data.randn(2, 3, 4, dtype=dsp.core.bf16)
        t = dsp.ops.transpose(x, -2, -1)
        assert list(t.shape) == [2, 4, 3]

    def test_custom_dims(self):
        x = dsp.data.randn(2, 3, 4, dtype=dsp.core.bf16)
        t = dsp.ops.transpose(x, 0, 2)
        assert list(t.shape) == [4, 3, 2]


class TestTransposeGoldenC:
    """golden_c 模式: 验证 dim0/dim1 透传到 call_c_func，并与 torch 结果一致。"""

    def setup_method(self):
        dsp.context.set_mode(Mode.GOLDEN_C)

    def teardown_method(self):
        dsp.context.set_mode(Mode.TORCH)

    def test_2d_last_two(self):
        x = dsp.data.tensor([[1, 2, 3], [4, 5, 6]], dtype=dsp.core.bf16)
        t = dsp.ops.transpose(x, -2, -1)
        assert list(t.shape) == [3, 2]
        assert t.torch().tolist() == [[1, 4], [2, 5], [3, 6]]

    def test_3d_last_two(self):
        # 用整数值避免 randn → _pre_quantize 导致的前置量化对照偏差
        data = [[[1, 2, 3, 4],
                 [5, 6, 7, 8],
                 [9, 10, 11, 12]],
                [[13, 14, 15, 16],
                 [17, 18, 19, 20],
                 [21, 22, 23, 24]]]
        x = dsp.data.tensor(data, dtype=dsp.core.bf16)
        t = dsp.ops.transpose(x, -2, -1)
        assert list(t.shape) == [2, 4, 3]
        import torch as _t
        assert _t.equal(t.torch(), x.torch().transpose(-2, -1).contiguous())

    def test_custom_dims_dim0_dim2(self):
        """验证 dim0/dim1 kwargs 真的透传到 golden_c 路径。"""
        data = [[[1, 2, 3, 4],
                 [5, 6, 7, 8],
                 [9, 10, 11, 12]],
                [[13, 14, 15, 16],
                 [17, 18, 19, 20],
                 [21, 22, 23, 24]]]
        x = dsp.data.tensor(data, dtype=dsp.core.bf16)
        t = dsp.ops.transpose(x, 0, 2)
        assert list(t.shape) == [4, 3, 2]
        import torch as _t
        assert _t.equal(t.torch(), x.torch().transpose(0, 2).contiguous())

    def test_custom_dims_dim1_dim2_4d(self):
        # 4D，验证 shape 正确且值按 dim1/dim2 对调
        x = dsp.data.tensor(
            [[[[i + j * 5 + k * 20 + b * 60 for i in range(5)]
               for k in range(4)] for j in range(3)] for b in range(2)],
            dtype=dsp.core.bf16,
        )
        t = dsp.ops.transpose(x, 1, 2)
        assert list(t.shape) == [2, 4, 3, 5]
        import torch as _t
        assert _t.equal(t.torch(), x.torch().transpose(1, 2).contiguous())
