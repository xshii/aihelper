"""golden convert 单元测试 — 公共 API dsp.golden.convert() + 原始 binding 往返。"""

import numpy as np
import pytest

from dsp.golden.call import _get_lib, convert, is_available


pytestmark = pytest.mark.skipif(not is_available(), reason="golden C not available")


@pytest.fixture
def lib():
    return _get_lib()


class TestConvertPublicAPI:
    """dsp.golden.call.convert() 高层 API —— double ↔ DUT。"""

    def test_double_to_bf16_to_double(self):
        src = np.array([1, 2, 3, -1, -2, 100, 0, -100], dtype=np.double)
        mid = convert(src, "double", "bf16")
        dst = convert(mid, "bf16", "double")
        assert mid.shape == src.shape
        assert dst.shape == src.shape
        np.testing.assert_array_almost_equal(src, dst, decimal=0)

    def test_double_to_bf8_to_double(self):
        # bf8 (fp8_e4m3) 精度低，只测 2 的幂次
        src = np.array([1, 2, 4, -1, -2, -4, 0, 8,
                        16, 32, 64, -16, -32, -64, 128, -128], dtype=np.double)
        mid = convert(src, "double", "bf8")
        dst = convert(mid, "bf8", "double")
        np.testing.assert_array_almost_equal(src, dst, decimal=0)

    def test_unknown_type_raises(self):
        src = np.zeros(8, dtype=np.double)
        with pytest.raises(Exception):
            convert(src, "double", "nope_not_a_type")


class TestConvertRoundtripRaw:
    """直接调 _raw_bindings 的 double ↔ DUT 往返。"""

    def test_bf16_roundtrip(self, lib):
        src = np.array([1, 2, 3, -1, -2, 100, 0, -100], dtype=np.double)
        mid = np.zeros(8, dtype=np.double)
        dst = np.zeros(8, dtype=np.double)
        lib.dsp_convert_double_bf16(src, mid, 8)
        lib.dsp_convert_bf16_double(mid, dst, 8)
        np.testing.assert_array_almost_equal(src, dst, decimal=0)

    def test_bf8_roundtrip(self, lib):
        src = np.array([1, 2, 4, -1, -2, -4, 0, 8,
                        16, 32, 64, -16, -32, -64, 128, -128], dtype=np.double)
        mid = np.zeros(16, dtype=np.double)
        dst = np.zeros(16, dtype=np.double)
        lib.dsp_convert_double_bf8(src, mid, 16)
        lib.dsp_convert_bf8_double(mid, dst, 16)
        np.testing.assert_array_almost_equal(src, dst, decimal=0)


class TestConvertAutoRegister:
    """auto_register 正确注册了 convert 函数。"""

    def test_convert_registered(self):
        from dsp.golden.manifest import CONVERT
        assert ("double", "bf16") in CONVERT
        assert ("bf16", "double") in CONVERT
        assert ("double", "bf8") in CONVERT
        assert ("bf8", "double") in CONVERT
