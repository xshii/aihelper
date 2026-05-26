from pa_debug.l1_transformer.rule import Arg, Rule


def _rule() -> Rule:
    return Rule(
        macro="M",
        op="OP",
        args=[
            Arg("op_id", role="id"),
            Arg("a", role="in"),
            Arg("b", role="in"),
            Arg("c", role="out"),
            Arg("m", role="meta"),
        ],
    )


def test_input_indices_returns_in_role_positions():
    assert _rule().input_indices() == [1, 2]


def test_output_indices_returns_out_role_positions():
    assert _rule().output_indices() == [3]


def test_id_index_returns_first_id_position():
    assert _rule().id_index() == 0


def test_id_index_is_minus_one_when_no_id_arg():
    rule = Rule(macro="M", op="OP", args=[Arg("a", role="in")])
    assert rule.id_index() == -1
