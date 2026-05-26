from pa_debug.l1_transformer.edits import Edit, apply_edits


def test_pure_insertions_keep_offsets_valid():
    src = "AAABBB"
    edits = [Edit(offset=3, length=0, replacement="<>"), Edit(offset=0, length=0, replacement="[]")]
    assert apply_edits(src, edits) == "[]AAA<>BBB"


def test_replacement():
    src = "hello world"
    edits = [Edit(offset=6, length=5, replacement="there")]
    assert apply_edits(src, edits) == "hello there"


def test_multiple_edits_applied_in_reverse():
    src = "0123456789"
    edits = [Edit(offset=2, length=0, replacement="A"), Edit(offset=8, length=0, replacement="B")]
    assert apply_edits(src, edits) == "01A234567B89"
