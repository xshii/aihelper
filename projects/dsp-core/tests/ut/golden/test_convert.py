"""golden convert binding 单元测试 — double ↔ DUT 往返。"""

import numpy as np
import pytest

from dsp.golden.call import _get_lib, is_available


@pytest.fixture
def lib():
    if not is_available():
        pytest.skip("golden C not available")
    return _get_lib()


class TestConvertRoundtrip:
    """double → DUT → double 往返（容忍浮点量化误差）。"""

    def test_bf16_roundtrip(self, lib):
        """bf16 能精确表示小整数。"""
        src = np.array([1, 2, 3, -1, -2, 100, 0, -100], dtype=np.double)
        mid = np.zeros(8, dtype=np.double)
        dst = np.zeros(8, dtype=np.double)
        lib.dsp_convert_double_bf16(src, mid, 8)
        lib.dsp_convert_bf16_double(mid, dst, 8)
        np.testing.assert_array_almost_equal(src, dst, decimal=0)

    def test_bf8_roundtrip(self, lib):
        """bf8 (fp8_e4m3) 精度低，只测试小值。"""
        src = np.array([1, 2, 4, -1, -2, -4, 0, 8,
                        16, 32, 64, -16, -32, -64, 128, -128], dtype=np.double)
        mid = np.zeros(16, dtype=np.double)
        dst = np.zeros(16, dtype=np.double)
        lib.dsp_convert_double_bf8(src, mid, 16)
        lib.dsp_convert_bf8_double(mid, dst, 16)
        # 2 的幂次能精确表示
        np.testing.assert_array_almost_equal(src, dst, decimal=0)


class TestConvertAutoRegister:
    """auto_register 正确注册了 convert 函数。"""

    def test_convert_registered(self):
        from dsp.golden.manifest import CONVERT
        assert ("double", "bf16") in CONVERT
        assert ("bf16", "double") in CONVERT
        assert ("double", "bf8") in CONVERT
        assert ("bf8", "double") in CONVERT
