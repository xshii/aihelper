"""frontend.iter_calls:从 TU 找 intrinsic 调用并按类型推断参数角色(需 libclang)。"""

import pytest

from pa_debug.l1_transformer.config import DiscoveryConfig
from pa_debug.l1_transformer.frontend import iter_calls, parse_source

pytestmark = pytest.mark.integration

HEADER = """typedef struct { unsigned opid; unsigned aopid; } commopheader;
static inline void pa_conv(commopheader* h, void* in, int n) {}
static inline void _emit(commopheader* h) {}
"""
SRC = """#include "intrinsics.h"
extern void* buf;
void layer3(void){ commopheader h = {0}; _emit(&h); pa_conv(&h, buf, 7); }
"""


def _parse(tmp_path):
    (tmp_path / "intrinsics.h").write_text(HEADER)
    c = tmp_path / "m.c"
    c.write_text(SRC)
    tu = parse_source(str(c), args=["-I", str(tmp_path)])
    return tu, c.read_bytes()


def _cfg() -> DiscoveryConfig:
    return DiscoveryConfig(intrinsic_headers=["intrinsics.h"], deny=[r"^_"])


def test_iter_calls_returns_only_intrinsic_calls(tmp_path):
    tu, data = _parse(tmp_path)
    calls = iter_calls(tu, data, _cfg())
    assert [c.op for c in calls] == ["pa_conv"]  # _emit denied, no system calls


def test_iter_calls_infers_role_and_arg_text(tmp_path):
    tu, data = _parse(tmp_path)
    call = iter_calls(tu, data, _cfg())[0]
    assert [(a.name, a.expr, a.role) for a in call.args] == [
        ("h", "&h", "struct"),
        ("in", "buf", "opaque"),
        ("n", "7", "meta"),
    ]


def test_iter_calls_expands_struct_fields_with_fmt(tmp_path):
    tu, data = _parse(tmp_path)
    call = iter_calls(tu, data, _cfg())[0]
    h = call.args[0]
    assert [(f.name, f.fmt) for f in h.fields] == [("opid", "%u"), ("aopid", "%u")]
    assert h.deref == "->"


def test_iter_calls_opaque_and_meta_fmt(tmp_path):
    tu, data = _parse(tmp_path)
    args = {a.name: a for a in iter_calls(tu, data, _cfg())[0].args}
    assert args["in"].fmt == "%p"
    assert args["n"].fmt == "%d"
