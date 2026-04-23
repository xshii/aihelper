"""run_deploy - mock subprocess 验证命令行组装（cli_vars + vars_file）"""
from __future__ import annotations

from pathlib import Path
from unittest import mock

from smartci.runner import run_deploy


def _fake_deploy():
    return mock.patch("smartci.runner.deploy_py", return_value=Path("/fake/deploy.py"))


def test_run_deploy_minimal_call(tmp_path):
    with mock.patch("smartci.runner.subprocess.run") as runfn, _fake_deploy():
        runfn.return_value = mock.Mock(returncode=0)
        rc = run_deploy(tmp_path / "m.json")

    assert rc == 0
    args = runfn.call_args.args[0]
    assert args[1] == "/fake/deploy.py"
    assert args[2].startswith("--manifest=")
    assert "-y" in args


def test_run_deploy_cli_vars_become_key_value_flags(tmp_path):
    cli_vars = {"team": "team-a", "platform": "fpga"}
    with mock.patch("smartci.runner.subprocess.run") as runfn, _fake_deploy():
        runfn.return_value = mock.Mock(returncode=0)
        run_deploy(tmp_path / "m.json", cli_vars=cli_vars)

    args = runfn.call_args.args[0]
    assert "--team=team-a" in args
    assert "--platform=fpga" in args


def test_run_deploy_vars_file_passed(tmp_path):
    vf = tmp_path / "vars.json"
    vf.write_text("{}", encoding="utf-8")
    with mock.patch("smartci.runner.subprocess.run") as runfn, _fake_deploy():
        runfn.return_value = mock.Mock(returncode=0)
        run_deploy(tmp_path / "m.json", vars_file=vf)

    args = runfn.call_args.args[0]
    assert f"--vars-file={vf}" in args


def test_run_deploy_auto_yes_false_omits_flag(tmp_path):
    with mock.patch("smartci.runner.subprocess.run") as runfn, _fake_deploy():
        runfn.return_value = mock.Mock(returncode=2)
        rc = run_deploy(tmp_path / "m.json", auto_yes=False)

    assert rc == 2
    assert "-y" not in runfn.call_args.args[0]
