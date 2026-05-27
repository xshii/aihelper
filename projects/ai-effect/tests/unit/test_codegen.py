"""dump 代码生成 + 语句定位(纯函数,验证精确输出)。"""

from pa_debug.l1_transformer.codegen import (
    indent_of,
    render_dump_call,
    render_dump_macro,
    statement_start,
)
from pa_debug.l1_transformer.config import DiscoveryConfig
from pa_debug.l1_transformer.model import Arg, FieldSpec

CFG = DiscoveryConfig(intrinsic_headers=["intrinsics.h"])


def test_render_dump_call_struct_opaque_meta():
    args = [
        Arg("h", "&h", "struct", fields=[FieldSpec("opid", "%u"), FieldSpec("aopid", "%u")]),
        Arg("in", "in_buf", "opaque", fmt="%p"),
        Arg("ish", "56", "meta", fmt="%d"),
    ]
    out = render_dump_call("pa_conv", "layer3", args, CFG)
    assert out == (
        'if (pa_dump_enabled) printf("{\\"kind\\":\\"call\\",\\"op\\":\\"pa_conv\\",'
        '\\"fn\\":\\"layer3\\",\\"h\\":{\\"opid\\":%u,\\"aopid\\":%u},'
        '\\"in\\":\\"%p\\",\\"ish\\":%d}\\n", '
        "(&h)->opid, (&h)->aopid, (void*)(in_buf), 56);"
    )


def test_render_dump_macro_dumps_raw_words_no_opid():
    out = render_dump_macro("hac_3r", ["MK_W0(h->opid)", "ish", "0"], CFG)
    assert out == (
        'if (pa_dump_enabled) printf("{\\"kind\\":\\"macro\\",\\"macro\\":\\"hac_3r\\",'
        '\\"words\\":[%u,%u,%u]}\\n", '
        "(unsigned)(MK_W0(h->opid)), (unsigned)(ish), (unsigned)(0));"
    )


def test_render_dump_macro_no_words():
    out = render_dump_macro("barrier", [], CFG)
    assert out == (
        'if (pa_dump_enabled) printf("{\\"kind\\":\\"macro\\",\\"macro\\":\\"barrier\\",'
        '\\"words\\":[]}\\n");'
    )


def test_render_uses_configured_print_fn_and_flag():
    cfg = DiscoveryConfig(intrinsic_headers=["x.h"], print_fn="plat_log", dump_flag="DBG")
    out = render_dump_call("op", "fn", [Arg("n", "7", "meta", fmt="%d")], cfg)
    assert out.startswith("if (DBG) plat_log(")


def test_statement_start_for_standalone_call_is_the_call():
    data = b"void f(void){\n    pa_conv(&h);\n}\n"
    call = data.index(b"pa_conv")
    assert statement_start(data, call) == call


def test_statement_start_for_call_in_initializer_is_the_declaration():
    data = b"void f(void){\n    commopheader h = {0};\n    int rc = pa_query(&h);\n}\n"
    call = data.index(b"pa_query")
    start = statement_start(data, call)
    assert data[start : start + 3] == b"int"


def test_indent_of_returns_leading_whitespace():
    data = b"void f(void){\n    pa_conv(&h);\n}\n"
    assert indent_of(data, data.index(b"pa_conv")) == "    "
