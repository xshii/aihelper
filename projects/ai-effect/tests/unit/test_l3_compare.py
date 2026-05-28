"""L3 通用比对:按 key 对齐两份导出,递归比任意嵌套结构,出字段级变更。"""

from pa_debug.l3_analyzer.compare import Change, diff_records


def test_added_op_reports_field_level_changes():
    report = diff_records([], [{"tid": 1, "iter": 0, "cu": 5}], ("tid", "iter"))
    assert len(report.diffs) == 1
    d = report.diffs[0]
    assert d.key == (1, 0)
    assert d.status == "added"
    assert Change("cu", None, 5) in d.changes


def test_removed_op():
    report = diff_records([{"tid": 1, "iter": 0, "cu": 5}], [], ("tid", "iter"))
    assert report.diffs[0].status == "removed"


def test_changed_scalar_field():
    left = [{"tid": 1, "iter": 0, "cu": 5}]
    right = [{"tid": 1, "iter": 0, "cu": 7}]
    d = diff_records(left, right, ("tid", "iter")).diffs[0]
    assert d.status == "changed"
    assert d.changes == [Change("cu", 5, 7)]


def test_nested_dict_change_reports_dotted_path():
    left = [{"tid": 1, "iter": 0, "cfg": {"a": 1, "b": 2}}]
    right = [{"tid": 1, "iter": 0, "cfg": {"a": 1, "b": 9}}]
    assert diff_records(left, right, ("tid", "iter")).diffs[0].changes == [Change("cfg.b", 2, 9)]


def test_list_element_change_reports_index_path():
    left = [{"tid": 1, "iter": 0, "deps": [{"slot": "A", "tid": 5}]}]
    right = [{"tid": 1, "iter": 0, "deps": [{"slot": "A", "tid": 6}]}]
    diffs = diff_records(left, right, ("tid", "iter")).diffs
    assert diffs[0].changes == [Change("deps[0].tid", 5, 6)]


def test_list_length_change():
    left = [{"tid": 1, "iter": 0, "deps": [1, 2]}]
    right = [{"tid": 1, "iter": 0, "deps": [1]}]
    diffs = diff_records(left, right, ("tid", "iter")).diffs
    assert diffs[0].changes == [Change("deps[1]", 2, None)]


def test_identical_records_produce_no_diff():
    rec = {"tid": 1, "iter": 0, "cu": 5, "deps": [{"slot": "A", "tid": 5}]}
    assert diff_records([rec], [dict(rec)], ("tid", "iter")).diffs == []


def test_same_tid_different_iter_aligned_separately():
    left = [{"tid": 1, "iter": 0, "cu": 5}, {"tid": 1, "iter": 1, "cu": 6}]
    right = [{"tid": 1, "iter": 0, "cu": 5}, {"tid": 1, "iter": 1, "cu": 99}]
    diffs = diff_records(left, right, ("tid", "iter")).diffs
    assert len(diffs) == 1
    assert diffs[0].key == (1, 1)
    assert diffs[0].changes == [Change("cu", 6, 99)]
