"""DeployRunner - mock subprocess 验证命令行组装 + manifest 写出"""
from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from smartci.const import (
    DEPLOY_AUTO_YES_ARG,
    DEPLOY_MANIFEST_ARG,
    DEPLOY_MANIFEST_FILENAME,
)
from smartci.runner import DeployRunner


def test_runner_writes_manifest_and_invokes_deploy_py(tmp_path):
    workdir = tmp_path / "run"
    manifest = {"variables": {"v": "1"}, "tasks": [{"name": "t", "usage": "echo"}]}

    with mock.patch("smartci.runner.subprocess.run") as runfn:
        runfn.return_value = mock.Mock(returncode=0)
        runner = DeployRunner(deploy_py=Path("/fake/deploy.py"))
        rc = runner.run(manifest, workdir, exec_cwd=tmp_path)

    assert rc == 0
    # manifest 被写到 workdir/manifest.json
    written = workdir / DEPLOY_MANIFEST_FILENAME
    assert written.exists()
    assert json.loads(written.read_text()) == manifest

    # subprocess 调用参数：python deploy.py --manifest=<path> -y
    args = runfn.call_args.args[0]
    assert args[1] == "/fake/deploy.py"
    assert args[2] == f"{DEPLOY_MANIFEST_ARG}={written}"
    assert DEPLOY_AUTO_YES_ARG in args


def test_runner_auto_yes_false_omits_flag(tmp_path):
    with mock.patch("smartci.runner.subprocess.run") as runfn:
        runfn.return_value = mock.Mock(returncode=2)
        runner = DeployRunner(deploy_py=Path("/fake/deploy.py"), auto_yes=False)
        rc = runner.run({"tasks": []}, tmp_path / "run")

    assert rc == 2
    args = runfn.call_args.args[0]
    assert DEPLOY_AUTO_YES_ARG not in args


def test_runner_default_deploy_py_resolves():
    """未指定 deploy_py 时 paths.deploy_py() 应返回一个以 deploy.py 结尾的路径。

    可能是 scripts/deploy.py（本仓自包含）或 ../dsp-integration/deploy.py（monorepo fallback）。
    """
    runner = DeployRunner()
    assert str(runner.deploy_py).endswith("deploy.py")
