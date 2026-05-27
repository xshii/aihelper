"""intrinsic 自动发现:头文件归属 + 正则黑白名单。"""

from pa_debug.l1_transformer.config import DiscoveryConfig
from pa_debug.l1_transformer.discovery import is_intrinsic


def _cfg(**kw) -> DiscoveryConfig:
    base = {"intrinsic_headers": ["intrinsics.h"], "allow": [], "deny": [r"^_"]}
    base.update(kw)
    return DiscoveryConfig(**base)


def test_call_defined_in_intrinsic_header_is_intrinsic():
    assert is_intrinsic("/proj/intrinsics.h", "pa_conv", _cfg())


def test_call_defined_elsewhere_is_not_intrinsic():
    assert not is_intrinsic("/usr/include/string.h", "memset", _cfg())


def test_unresolved_decl_file_is_not_intrinsic():
    assert not is_intrinsic(None, "pa_conv", _cfg())


def test_deny_regex_excludes_internal_helper():
    assert not is_intrinsic("/proj/intrinsics.h", "_emit", _cfg())


def test_allow_regex_limits_to_matching_names():
    cfg = _cfg(allow=[r"^pa_"])
    assert is_intrinsic("/proj/intrinsics.h", "pa_conv", cfg)
    assert not is_intrinsic("/proj/intrinsics.h", "hac_set", cfg)
