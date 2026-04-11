"""测试 golden 模块：manifest 查询 + call 接口。"""

import pytest
from dsp.core.dtype import DType
from dsp.golden.manifest import (
    ComputeKey, TYPES, COMPUTE, CONVERT,
    get_type_info, get_block_shape, require_convert_func,
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
        key = ComputeKey(op="matmul", src0=D.INT16, src1=D.INT16, dst0=D.INT32, acc=A.Q12_22, compute_dtype=D.INT16)
        assert key.op == "matmul"
        assert key.src0 == "int16"
        assert key.dst0 == "int32"
        assert key.acc == "q12.22"
        assert key.compute_dtype == "int16"
        assert key.src2 is None

    def test_get_type_info(self):
        info = get_type_info("int16")
        assert info is not None
        assert "block_shapes" in info
        assert get_type_info("nonexistent") is None

    def test_dtype_is_source_of_truth(self):
        """类型基础信息在 core/dtype.py，不在 manifest。"""
        from dsp.core.dtype import get_dtype
        d = get_dtype("int16")
        assert d.torch_dtype.is_signed

    def test_get_block_shape(self):
        assert get_block_shape("int16", "zz") == (16, 16)
        assert get_block_shape("int16", "nn") == (16, 32)
        assert get_block_shape("unknown", "zz") == (8, 8)  # fallback

    def test_require_convert_func(self):
        assert require_convert_func("int16", "float32") == "dsp_convert_int16_float32"

    def test_require_convert_func_not_found(self):
        import pytest
        with pytest.raises(Exception):
            require_convert_func("int16", "nonexistent")

    def test_get_compute_info(self):
        info = get_compute_info(ComputeKey(op="matmul", src0="int16", src1="int16"))
        assert info is not None
        key = info["key"]
        assert key.acc == A.Q12_22

    def test_get_compute_info_fused_linear(self):
        info = get_compute_info(ComputeKey(op="linear", src0="int16", src1="int16"))
        assert info is not None
        key = info["key"]
        assert key.acc == A.Q12_22

    def test_get_compute_info_not_found(self):
        assert get_compute_info(ComputeKey(op="nonexistent", src0="int16", src1="int16")) is None

    def test_list_types(self):
        types = list_types()
        assert "int16" in types
        assert "float32" in types

    def test_list_ops(self):
        ops = list_ops()
        assert "matmul" in ops
        assert "add" in ops

    def test_list_converts(self):
        convs = list_converts()
        assert ("int16", "float32") in convs


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
        # _raw_bindings 需要 make build-golden 编译
        # 但如果有 stub，可能可用 — 只测不抛异常
        result = is_available()
        assert isinstance(result, bool)
