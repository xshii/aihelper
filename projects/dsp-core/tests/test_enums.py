"""测试枚举类型。"""

import pytest
from dsp.core.enums import Mode, Format, RunMode
from dsp.core.dtype import DType

pytestmark = pytest.mark.ut


class TestMode:
    def test_values(self):
        assert Mode.TORCH == "torch"
        assert Mode.PSEUDO_QUANT == "pseudo_quant"
        assert Mode.GOLDEN_C == "golden_c"

    def test_is_str(self):
        assert isinstance(Mode.TORCH, str)

    def test_construct_from_str(self):
        assert Mode("torch") == Mode.TORCH


class TestFormat:
    def test_values(self):
        assert Format.ND == "nd"
        assert Format.ZZ == "zz"
        assert Format.NN == "nn"

    def test_construct_from_str(self):
        assert Format("zz") == Format.ZZ


class TestRunMode:
    def test_values(self):
        assert RunMode.GENERATE_INPUT == "generate_input"
        assert RunMode.USE_INPUT == "use_input"


class TestDType:
    def test_real(self):
        assert DType.REAL.DOUBLE == "double"

    def test_dut(self):
        assert DType.DUT.BINT8 == "bint8"
        assert DType.DUT.BINT16 == "bint16"

    def test_acc(self):
        assert DType.ACC.Q12_22 == "q12.22"
        assert DType.ACC.Q8_26 == "q8.26"
        assert DType.ACC.Q24_40 == "q24.40"

    def test_int32_is_dut(self):
        assert DType.DUT.BINT32 == "bint32"

    def test_is_str(self):
        assert isinstance(DType.DUT.BINT16, str)
        assert isinstance(DType.ACC.Q12_22, str)
        assert isinstance(DType.REAL.DOUBLE, str)

    def test_hierarchy(self):
        """三级分类互不冲突。"""
        all_values = (
            [m.value for m in DType.REAL]
            + [m.value for m in DType.DUT]
            + [m.value for m in DType.ACC]
        )
        assert len(all_values) == len(set(all_values))
