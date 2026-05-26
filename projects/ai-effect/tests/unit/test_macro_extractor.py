from pa_debug.l1_transformer.frontend import parse_source
from pa_debug.l1_transformer.macro_extractor import find_macro_calls

SRC = """#include "pa_intrinsics.h"
void f(pa_tensor_t* in, pa_tensor_t* w, pa_tensor_t* out) {
    PA_INSTR_CONV(c0, in, w, out, s1, s2, s3);
}
"""


def test_extract_one_call(tmp_path, stub_include_args):
    src = tmp_path / "f.c"
    src.write_text(SRC)
    tu = parse_source(str(src), args=stub_include_args)
    calls = find_macro_calls(tu, src.read_bytes(), "PA_INSTR_CONV")
    assert len(calls) == 1
    c = calls[0]
    assert c.name == "PA_INSTR_CONV"
    assert c.args == ["c0", "in", "w", "out", "s1", "s2", "s3"]
    assert SRC.encode()[c.start_offset :].startswith(b"PA_INSTR_CONV")
    assert SRC.encode()[c.end_offset - 1 : c.end_offset] == b")"


ALIAS_SRC = """#include "pa_intrinsics.h"
void f(pa_tensor_t* in, pa_tensor_t* w, pa_tensor_t* out) {
    PA_CONV(c0, in, w, out, s1, s2, s3);
}
"""


def test_alias_is_matched_as_canonical_macro(tmp_path, stub_include_args):
    src = tmp_path / "f.c"
    src.write_text(ALIAS_SRC)
    tu = parse_source(str(src), args=stub_include_args)
    calls = find_macro_calls(
        tu, src.read_bytes(), "PA_INSTR_CONV", aliases={"PA_CONV": "PA_INSTR_CONV"}
    )
    assert len(calls) == 1
    assert calls[0].args == ["c0", "in", "w", "out", "s1", "s2", "s3"]
