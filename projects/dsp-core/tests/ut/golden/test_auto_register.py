"""auto_register 单元测试 — 验证注册机制，不绑定具体函数名。"""

import pytest
from dsp.golden.call import is_available
from dsp.golden.manifest import COMPUTE, CONVERT, _COMPUTE_BY_OP


@pytest.fixture(autouse=True)
def require_golden():
    if not is_available():
        pytest.skip("golden C not available")


class TestAutoRegister:
    def test_convert_not_empty(self):
        assert len(CONVERT) > 0

    def test_compute_not_empty(self):
        assert len(COMPUTE) > 0

    def test_ops_include_linear(self):
        assert "linear" in _COMPUTE_BY_OP

    def test_ops_include_layernorm1d(self):
        assert "layernorm1d" in _COMPUTE_BY_OP
