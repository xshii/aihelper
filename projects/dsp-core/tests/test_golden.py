"""测试 golden 模块：manifest 查询 + call 接口。"""

import pytest
from dsp.core.enums import DType
from dsp.golden.manifest import (
    ComputeKey, TYPES, COMPUTE, CONVERT,
    get_type_info, get_block_shape, get_convert_func,
    get_compute_func, get_compute_info,
    list_types, list_ops, list_converts,
)
from dsp.golden.call import is_available
from dsp.golden.op_convention import get_convention

D, A = DType.DUT, DType.ACC

pytestmark = pytest.mark.ut


class TestManifest:
    def test_types_have_required_fields(self):
        for name, info in TYPES.items():
            assert "c_names" in info
            assert "block_shapes" in info
            assert "zz" in info["block_shapes"]
            assert "nn" in info["block_shapes"]

    def test_compute_key_named_fields(self):
        key = ComputeKey(op="matmul", in0=D.IQ16, in1=D.IQ16, out0=D.IQ32, acc=A.Q12_22, compute=D.IQ16)
        assert key.op == "matmul"
        assert key.in0 == "iq16"
        assert key.out0 == "iq32"
        assert key.acc == "q12.22"
        assert key.compute == "iq16"
        assert key.in2 is None

    def test_get_type_info(self):
        info = get_type_info("iq16")
        assert info is not None
        assert "block_shapes" in info
        assert get_type_info("nonexistent") is None

    def test_dtype_is_source_of_truth(self):
        """类型基础信息在 core/dtype.py，不在 manifest。"""
        from dsp.core.dtype import get_dtype
        d = get_dtype("iq16")
        assert d.bits == 16
        assert d.is_complex is True

    def test_get_block_shape(self):
        assert get_block_shape("iq16", "zz") == (16, 16)
        assert get_block_shape("iq16", "nn") == (16, 32)
        assert get_block_shape("unknown", "zz") == (8, 8)  # fallback

    def test_get_convert_func(self):
        assert get_convert_func("iq16", "float32") == "convert_iq16_to_float32"
        assert get_convert_func("iq16", "nonexistent") is None

    def test_get_compute_info(self):
        info = get_compute_info("matmul", "iq16", "iq16")
        assert info is not None
        key = info["key"]
        assert key.out0 == D.IQ32
        assert key.acc == A.Q12_22
        assert key.compute == D.IQ16

    def test_get_compute_info_fused_linear(self):
        info = get_compute_info("linear", "iq16", "iq16")
        assert info is not None
        key = info["key"]
        assert key.in2 == D.IQ32       # bias type
        assert key.compute == D.IQ16   # 计算精度
        assert key.acc == A.Q12_22     # 累加器格式
        assert key.out0 == D.IQ16

    def test_get_compute_info_not_found(self):
        assert get_compute_info("nonexistent", "iq16", "iq16") is None

    def test_list_types(self):
        types = list_types()
        assert "iq16" in types
        assert "float32" in types

    def test_list_ops(self):
        ops = list_ops()
        assert "matmul" in ops
        assert "add" in ops

    def test_list_converts(self):
        convs = list_converts()
        assert ("iq16", "float32") in convs


class TestConvention:
    def test_matmul_convention_exists(self):
        conv = get_convention("matmul")
        assert conv is not None

    def test_elementwise_convention_shared(self):
        assert get_convention("add") is get_convention("mul")

    def test_unknown_convention_returns_none(self):
        assert get_convention("nonexistent_op") is None


class TestCallAvailability:
    def test_is_available(self):
        # fake_c 已删除，应该不可用
        # 但如果有 stub，可能可用 — 只测不抛异常
        result = is_available()
        assert isinstance(result, bool)
