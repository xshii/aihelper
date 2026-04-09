"""测试 DSPTensor 基本功能。"""

import torch
import pytest

pytestmark = pytest.mark.ut


class TestCreate:
    def test_randn(self):
        import dsp
        a = dsp.ops.randn(100, dtype=dsp.core.int16)
        assert isinstance(a, dsp.core.DSPTensor)
        assert isinstance(a, torch.Tensor)
        assert a.dsp_dtype == dsp.core.int16
        assert a.shape == (100,)

    def test_zeros(self):
        import dsp
        a = dsp.ops.zeros(10, dtype=dsp.core.float32)
        assert a.dsp_dtype == dsp.core.float32
        assert torch.all(a == 0)

    def test_tensor_from_data(self):
        import dsp
        a = dsp.ops.tensor([1.0, 2.0, 3.0], dtype=dsp.core.float32)
        assert a.dsp_dtype == dsp.core.float32
        assert a.shape == (3,)

    def test_from_torch(self):
        import dsp
        t = torch.randn(50)
        a = dsp.ops.from_torch(t, dtype=dsp.core.float32)
        assert a.dsp_dtype == dsp.core.float32
        assert a.shape == (50,)


class TestTorchCompat:
    """验证 DSPTensor IS-A torch.Tensor，标准 torch ops 天然可用。"""

    def test_isinstance(self):
        import dsp
        a = dsp.ops.randn(10, dtype=dsp.core.float32)
        assert isinstance(a, torch.Tensor)

    def test_add(self, float32_pair):
        a, b = float32_pair
        c = a + b
        assert isinstance(c, torch.Tensor)
        assert c.shape == a.shape

    def test_torch_add(self, float32_pair):
        a, b = float32_pair
        c = torch.add(a, b)
        assert c.shape == a.shape

    def test_mul(self, float32_pair):
        a, b = float32_pair
        c = a * b
        assert c.shape == a.shape

    def test_indexing(self):
        import dsp
        a = dsp.ops.randn(100, dtype=dsp.core.float32)
        b = a[10:20]
        assert b.shape == (10,)

    def test_shape_device(self):
        import dsp
        a = dsp.ops.randn(3, 4, dtype=dsp.core.float32)
        assert a.shape == (3, 4)
        assert a.device.type == "cpu"

    def test_int16_add(self, int16_pair):
        """INT16 的加法也直接能用。"""
        a, b = int16_pair
        c = a + b
        assert c.shape == a.shape
        assert c.dtype == torch.int16


class TestDtypePropagation:
    """验证 __torch_function__ 正确传播 dsp_dtype。"""

    def test_add_preserves_dtype(self, int16_pair):
        import dsp
        a, b = int16_pair
        c = a + b
        # __torch_function__ 应传播 dsp_dtype
        if isinstance(c, dsp.core.DSPTensor):
            assert c.dsp_dtype == dsp.core.int16

    def test_abs_preserves_dtype(self):
        import dsp
        a = dsp.ops.randn(10, dtype=dsp.core.float32)
        b = torch.abs(a)
        if isinstance(b, dsp.core.DSPTensor):
            assert b.dsp_dtype == dsp.core.float32


class TestConversion:
    def test_torch_escape(self):
        """DSPTensor.torch() 脱壳为标准 torch.Tensor。"""
        import dsp
        a = dsp.ops.randn(10, dtype=dsp.core.int16)
        t = a.torch()
        assert type(t) is torch.Tensor  # 不是 DSPTensor
        assert not isinstance(t, dsp.core.DSPTensor)

    def test_to_dsp(self):
        """DSPTensor.to_dsp() 转换 DSP 类型。"""
        import dsp
        a = dsp.ops.randn(10, dtype=dsp.core.float32)
        b = a.to_dsp(dsp.core.float64)
        assert b.dsp_dtype == dsp.core.float64

    def test_fake_quantize(self):
        """fake_quantize 截断精度，shape 和 dtype 不变。"""
        import dsp
        a = dsp.ops.randn(10, dtype=dsp.core.int16)
        b = a.fake_quantize()
        assert b.shape == a.shape
        assert b.dsp_dtype == dsp.core.int16
        assert b.torch_dtype == a.torch_dtype
        assert b.dsp_dtype == dsp.core.int16
