"""依赖表抽取(②):begin/end 聚合 + 写死公共头切片 + bitmap 过滤。"""

import pytest

from pa_debug.l3_analyzer.deps import (
    OP_COMM_HEADER,
    DepConfig,
    Dependency,
    DepSlot,
    HeaderField,
    aggregate_by_marker,
    extract_dependency_table,
    slice_header,
)
from pa_debug.l3_analyzer.model import DecodeError

# 假涉密值:末位 word == 0xBB 为 begin、== 0xEE 为 end;word 位宽 8。
CFG = DepConfig(begin_mask=0xFF, begin_value=0xBB, end_mask=0xFF, end_value=0xEE, word_bits=8)

# 测试用小布局(每字段 8 位 = 一个 word),与框架默认 OP_COMM_HEADER 解耦。
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


def test_aggregate_brackets_one_op_between_begin_and_end():
    records = [_macro([1, 2, 0xBB]), _macro([3, 4]), _macro([5, 0xEE])]
    assert aggregate_by_marker(records, CFG) == [[1, 2, 0xBB, 3, 4, 5, 0xEE]]


def test_aggregate_skips_call_records():
    records = [{"kind": "call", "op": "pa_conv", "fn": "f"}, _macro([9, 0xBB]), _macro([0xEE])]
    assert aggregate_by_marker(records, CFG) == [[9, 0xBB, 0xEE]]


def test_aggregate_two_ops():
    records = [_macro([1, 0xBB]), _macro([0xEE]), _macro([2, 0xBB]), _macro([0xEE])]
    assert aggregate_by_marker(records, CFG) == [[1, 0xBB, 0xEE], [2, 0xBB, 0xEE]]


def test_macro_before_begin_raises():
    with pytest.raises(DecodeError):
        aggregate_by_marker([_macro([1, 2])], CFG)


def test_missing_end_raises():
    with pytest.raises(DecodeError):
        aggregate_by_marker([_macro([1, 0xBB])], CFG)


def test_slice_header_reads_fields_lsb_first():
    header = slice_header([100, 3, 0b101, 50, 51, 52], CFG, LAYOUT)
    assert header == {
        "tid": 100,
        "curComputeUnit": 3,
        "depentUint": 0b101,
        "dependAtid": 50,
        "dependBtid": 51,
        "dependCtid": 52,
    }


def test_short_stream_raises():
    with pytest.raises(DecodeError):
        slice_header([1, 2], CFG, LAYOUT)  # 不足 6 个字段


def test_extract_table_filters_deps_by_bitmap():
    # 公共头 6 word + begin 标记;bitmap=0b101 → 只留 A、C
    op = _macro([100, 3, 0b101, 50, 51, 52, 0xBB])
    end = _macro([0xEE])
    table = extract_dependency_table([op, end], CFG, layout=LAYOUT, dep_slots=SLOTS)
    assert len(table) == 1
    assert table[0].tid == 100
    assert table[0].cur_compute_unit == 3
    assert table[0].deps == [Dependency("A", 50), Dependency("C", 52)]


def test_shipped_default_header_layout_slices_known_stream():
    # 校验框架自带的 OP_COMM_HEADER 默认值能正确切一条 32 位 word 流
    cfg = DepConfig(begin_mask=0, begin_value=0, end_mask=0, end_value=0, word_bits=32)
    words = [
        (0xAA << 24) | (0x05 << 16) | 0x1234,  # rsv=0xAA | curComputeUnit=0x05 | tid=0x1234
        (60 << 16) | 0b011,  # dependAtid=60 | depentUint=0b011
        (62 << 16) | 61,  # dependCtid=62 | dependBtid=61
    ]
    header = slice_header(words, cfg, OP_COMM_HEADER)
    assert header["tid"] == 0x1234
    assert header["curComputeUnit"] == 0x05
    assert header["depentUint"] == 0b011
    assert (header["dependAtid"], header["dependBtid"], header["dependCtid"]) == (60, 61, 62)
