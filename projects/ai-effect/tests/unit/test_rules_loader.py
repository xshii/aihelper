"""验证规则隔离:规则实例外置在目录里,框架动态加载,新增规则不改框架代码。"""

import textwrap
from pathlib import Path

import pytest

from pa_debug.l1_transformer.rules_loader import load_aliases, load_blacklist, load_rules

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body))


def test_loads_rule_defined_in_external_file(tmp_path):
    _write(
        tmp_path / "relu.py",
        """
        from pa_debug.l1_transformer.rule import Arg, Rule

        RULE = Rule(
            macro="PA_INSTR_RELU",
            op="RELU",
            args=[Arg("op_id", role="id"), Arg("x", role="in"), Arg("y", role="out")],
        )
        """,
    )
    rules = load_rules(tmp_path)
    assert [r.macro for r in rules] == ["PA_INSTR_RELU"]
    assert rules[0].op == "RELU"


def test_ignores_modules_without_rule(tmp_path):
    _write(
        tmp_path / "conv.py",
        """
        from pa_debug.l1_transformer.rule import Arg, Rule

        RULE = Rule(macro="PA_INSTR_CONV", op="CONV", args=[Arg("op_id", role="id")])
        """,
    )
    _write(tmp_path / "blacklist.py", "SKIP_FILES = ['foo.c']\n")
    rules = load_rules(tmp_path)
    assert [r.macro for r in rules] == ["PA_INSTR_CONV"]


def test_supports_rules_list_attribute(tmp_path):
    _write(
        tmp_path / "many.py",
        """
        from pa_debug.l1_transformer.rule import Rule

        RULES = [Rule(macro="A", op="A"), Rule(macro="B", op="B")]
        """,
    )
    assert {r.macro for r in load_rules(tmp_path)} == {"A", "B"}


def test_missing_directory_raises(tmp_path):
    with pytest.raises(NotADirectoryError):
        load_rules(tmp_path / "does_not_exist")


def test_loads_project_conv_rule_from_rules_dir():
    rules = load_rules(PROJECT_ROOT / "rules")
    assert "PA_INSTR_CONV" in {r.macro for r in rules}


def test_load_aliases_reads_isomorphisms(tmp_path):
    _write(tmp_path / "isomorphisms.py", "ALIASES = {'PA_CONV': 'PA_INSTR_CONV'}\n")
    assert load_aliases(tmp_path) == {"PA_CONV": "PA_INSTR_CONV"}


def test_load_aliases_empty_when_absent(tmp_path):
    assert load_aliases(tmp_path) == {}


def test_load_blacklist_reads_lists(tmp_path):
    _write(tmp_path / "blacklist.py", "SKIP_FILES = ['gen.c']\nSKIP_FUNCTIONS = ['init']\n")
    blacklist = load_blacklist(tmp_path)
    assert blacklist.skip_files == ["gen.c"]
    assert blacklist.skip_functions == ["init"]


def test_load_blacklist_empty_when_absent(tmp_path):
    blacklist = load_blacklist(tmp_path)
    assert blacklist.skip_files == []
    assert blacklist.skip_functions == []
