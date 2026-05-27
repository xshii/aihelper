"""frontend.iter_macro_calls:在 inline 函数体(含嵌套辅助)里找硬件宏调用(需 libclang)。"""

import pytest

from pa_debug.l1_transformer.frontend import iter_macro_calls, parse_source

pytestmark = pytest.mark.integration

HEADER = """typedef struct { unsigned opid; } commopheader;
#define MK_W0(x) (0x5A0000u | ((x) & 0xFFFFu))
#define hac_3r(w0,w1,w2) do { (void)(w0);(void)(w1);(void)(w2); } while(0)
#define hac_2r(w0,w1)    do { (void)(w0);(void)(w1); } while(0)
static inline void _emit(commopheader* h, int ish) {
    hac_3r(MK_W0(h->opid), ish, 0);
}
static inline void pa_conv(commopheader* h, int ish) {
    _emit(h, ish);
    hac_2r(1, ish);
}
"""


def _parse(tmp_path):
    p = tmp_path / "intrinsics.h"
    p.write_text(HEADER)
    return parse_source(str(p), args=["-x", "c"]), p.read_bytes()


def test_finds_hardware_macros_in_nested_and_top_in_source_order(tmp_path):
    tu, data = _parse(tmp_path)
    calls = iter_macro_calls(tu, data, ["hac_2r", "hac_3r"])
    assert [(c.name, c.words) for c in calls] == [
        ("hac_3r", ["MK_W0(h->opid)", "ish", "0"]),  # 在二级辅助 _emit 内
        ("hac_2r", ["1", "ish"]),  # 在顶层 pa_conv 内
    ]


def test_ignores_macros_not_in_list(tmp_path):
    tu, data = _parse(tmp_path)
    calls = iter_macro_calls(tu, data, ["hac_2r"])
    assert [c.name for c in calls] == ["hac_2r"]  # MK_W0 / hac_3r 不在清单
