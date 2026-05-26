from pa_debug.l1_transformer.frontend import macro_instantiations, parse_source

SRC = """#include "pa_intrinsics.h"
void f(pa_tensor_t* in, pa_tensor_t* w, pa_tensor_t* out) {
    PA_INSTR_CONV(c0, in, w, out, s1, s2, s3);
}
"""


def test_parse_no_fatal_errors(tmp_path, stub_include_args):
    src = tmp_path / "f.c"
    src.write_text(SRC)
    tu = parse_source(str(src), args=stub_include_args)
    fatals = [d for d in tu.diagnostics if d.severity >= 4]
    assert fatals == []


def test_finds_macro_instantiation(tmp_path, stub_include_args):
    src = tmp_path / "f.c"
    src.write_text(SRC)
    tu = parse_source(str(src), args=stub_include_args)
    names = [m.spelling for m in macro_instantiations(tu)]
    assert "PA_INSTR_CONV" in names
