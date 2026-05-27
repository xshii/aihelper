"""硬件宏 word 提取:从宏名偏移找平衡括号,按顶层逗号切分(纯函数)。"""

from pa_debug.l1_transformer.arg_splitter import extract_words


def test_simple_args():
    assert extract_words(b"hac_3r(a, b, c);", 0) == ["a", "b", "c"]


def test_nested_parens_not_split():
    assert extract_words(b"hac_3r(MK_W0(h->opid), ish, 0);", 0) == ["MK_W0(h->opid)", "ish", "0"]


def test_whitespace_before_paren():
    assert extract_words(b"hac_2r  (x, y)", 0) == ["x", "y"]


def test_comma_inside_string_not_split():
    assert extract_words(b'log("a,b", c)', 0) == ['"a,b"', "c"]


def test_no_args():
    assert extract_words(b"barrier()", 0) == []


def test_name_offset_into_larger_buffer():
    data = b"    hac_2r(1, ish);\n"
    assert extract_words(data, 4) == ["1", "ish"]
