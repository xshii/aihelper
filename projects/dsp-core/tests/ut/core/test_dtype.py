"""core/dtype.py 单元测试 — 机制验证，不绑定具体类型值。"""

import pytest

from dsp.core.dtype import (
    DSPDtype, bf16, double,
    get_dtype, list_dtypes, get_codec,
)


class TestDSPDtype:
    def test_repr(self):
        assert "dsp." in repr(bf16)

    def test_equality(self):
        assert bf16 == bf16
        assert bf16 != double

    def test_hash(self):
        d = {bf16: "ok"}
        assert d[bf16] == "ok"


class TestDtypeRegistry:
    def test_get_known(self):
        d = get_dtype(bf16.name)
        assert d is bf16

    def test_get_unknown(self):
        with pytest.raises(ValueError):
            get_dtype("nonexistent")

    def test_list_not_empty(self):
        assert len(list_dtypes()) >= 2


class TestCodec:
    def test_every_dtype_has_codec(self):
        """所有注册的 dtype 都有 codec。"""
        for name in list_dtypes():
            d = get_dtype(name)
            codec = get_codec(d)
            assert codec is not None
