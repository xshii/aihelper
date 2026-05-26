import pytest

from pa_debug.l1_transformer.arg_splitter import split_args

CASES = [
    ("simple", "a, b, c", ["a", "b", "c"]),
    ("nested_call", "a, foo(b, c), d", ["a", "foo(b, c)", "d"]),
    ("nested_brackets_braces", "a, x[1, 2], (int[]){3, 4}", ["a", "x[1, 2]", "(int[]){3, 4}"]),
    ("deep_nesting", "f(g(h(1, 2)), 3), b", ["f(g(h(1, 2)), 3)", "b"]),
    ("string_with_comma", 'a, "x, y", c', ["a", '"x, y"', "c"]),
    ("char_literal_with_comma", "a, ',', c", ["a", "','", "c"]),
    ("escaped_quote_in_string", r'"a\"b, c", d', [r'"a\"b, c"', "d"]),
    ("whitespace_trimmed", "  a ,  b  ", ["a", "b"]),
    ("empty_middle_arg", "a, , c", ["a", "", "c"]),
    ("single", "only", ["only"]),
    ("empty", "", []),
]


@pytest.mark.parametrize(
    "text, expected", [(t, e) for _, t, e in CASES], ids=[name for name, _, _ in CASES]
)
def test_split_args(text, expected):
    assert split_args(text) == expected
