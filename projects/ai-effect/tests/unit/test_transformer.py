import pytest

from pa_debug.l1_transformer.transformer import at_statement_position

# before = 宏名之前的源码片段;guard 判断宏是否"独立成句"
STATEMENT = [
    ("", "文件首"),
    ("{", "块起始"),
    ("}", "前一块结束"),
    ("int x = 0;", "前一语句的分号"),
    ("int x = 0;\n    ", "分号后换行缩进"),
    ("   ", "仅空白"),
]
NOT_STATEMENT = [
    ("x = ", "赋值右侧(表达式位置)"),
    ("return ", "return 表达式"),
    ("foo(", "调用实参"),
    ("if (cond) ", "无大括号 if 体,插桩会改变语义"),
]


@pytest.mark.parametrize("before", [b for b, _ in STATEMENT], ids=[d for _, d in STATEMENT])
def test_statement_position_accepted(before):
    data = (before + "PA_X(a)").encode()
    assert at_statement_position(data, len(before.encode())) is True


@pytest.mark.parametrize("before", [b for b, _ in NOT_STATEMENT], ids=[d for _, d in NOT_STATEMENT])
def test_non_statement_position_rejected(before):
    data = (before + "PA_X(a)").encode()
    assert at_statement_position(data, len(before.encode())) is False
