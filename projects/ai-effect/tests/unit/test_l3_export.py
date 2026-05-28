"""L3 导出:依赖表 → 每条配 iter(同 tid 第几次出现)→ 可序列化记录。"""

from pa_debug.l3_analyzer.deps import DepConfig, DepSlot, HeaderField
from pa_debug.l3_analyzer.export import export_dependencies

CFG = DepConfig(begin_mask=0xFF, begin_value=0xBB, end_mask=0xFF, end_value=0xEE, word_bits=8)
LAYOUT = [
    HeaderField("tid", 8),
    HeaderField("curComputeUnit", 8),
    HeaderField("depentUint", 8),
    HeaderField("dependAtid", 8),
    HeaderField("dependBtid", 8),
    HeaderField("dependCtid", 8),
]
SLOTS = [DepSlot("A", "dependAtid"), DepSlot("B", "dependBtid"), DepSlot("C", "dependCtid")]


def _macro(words: list[int], name: str = "hac_2r") -> dict:
    return {"kind": "macro", "macro": name, "words": words}


def test_iter_increments_per_tid():
    recs = [
        _macro([100, 3, 0b001, 50, 51, 52, 0xBB]),
        _macro([0xEE]),
        _macro([100, 4, 0b000, 0, 0, 0, 0xBB]),
        _macro([0xEE]),
    ]
    out = export_dependencies(recs, CFG, layout=LAYOUT, dep_slots=SLOTS)
    assert [(r["tid"], r["iter"]) for r in out] == [(100, 0), (100, 1)]


def test_export_record_shape():
    recs = [_macro([100, 3, 0b101, 50, 51, 52, 0xBB]), _macro([0xEE])]
    out = export_dependencies(recs, CFG, layout=LAYOUT, dep_slots=SLOTS)
    assert out == [
        {
            "tid": 100,
            "iter": 0,
            "curComputeUnit": 3,
            "deps": [{"slot": "A", "tid": 50}, {"slot": "C", "tid": 52}],
        }
    ]
