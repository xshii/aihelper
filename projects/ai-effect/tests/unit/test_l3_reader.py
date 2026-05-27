"""L3-a 聚合阅读器:trace 记录 → 按执行顺序 bracketing 聚成 OpRecord。"""

import pytest

from pa_debug.l3_analyzer.model import DecodeError
from pa_debug.l3_analyzer.reader import aggregate, load_trace


def test_aggregate_groups_call_with_following_macros():
    records = [
        {"kind": "call", "op": "pa_conv", "fn": "layer3", "h": {"opid": 42}, "ish": 8},
        {"kind": "macro", "macro": "hac_3r", "words": [1, 2, 3]},
        {"kind": "call", "op": "pa_pool", "fn": "layer3", "h": {"opid": 43}},
        {"kind": "macro", "macro": "hac_2r", "words": [4, 5]},
    ]
    ops = aggregate(records)
    assert [o.op for o in ops] == ["pa_conv", "pa_pool"]
    assert ops[0].fields == {"h": {"opid": 42}, "ish": 8}
    assert [(m.name, m.words) for m in ops[0].macros] == [("hac_3r", [1, 2, 3])]
    assert [m.name for m in ops[1].macros] == ["hac_2r"]


def test_macro_before_any_call_raises():
    with pytest.raises(DecodeError):
        aggregate([{"kind": "macro", "macro": "x", "words": [1]}])


def test_load_trace_reads_jsonl(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text('{"kind":"call","op":"a"}\n\n{"kind":"macro","macro":"m","words":[1]}\n')
    assert load_trace(p) == [
        {"kind": "call", "op": "a"},
        {"kind": "macro", "macro": "m", "words": [1]},
    ]
