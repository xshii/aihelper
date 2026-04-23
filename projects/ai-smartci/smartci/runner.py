"""run_deploy - subprocess 调用 deploy.py 的薄包装

PURPOSE:
  smartci 不自己实现流水线调度。读 platforms/*/{xxx}.manifest.json，
  可选带上:
    - cli_vars: 动态 CLI 参数（platform/team/...），以 --key=value 透传
    - vars_file: 仓内固化的静态公参 JSON（artifact_endpoint 等常量），
                 走 deploy.py 的 --vars-file
  不写任何临时文件。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

from smartci.common.paths import deploy_py
from smartci.const import DEPLOY_AUTO_YES_ARG, DEPLOY_MANIFEST_ARG


def run_deploy(
    manifest: Path,
    cli_vars: Optional[Dict[str, str]] = None,
    vars_file: Optional[Path] = None,
    auto_yes: bool = True,
) -> int:
    """subprocess 调起 deploy.py，返回 returncode。

    优先级（低→高覆盖，由 deploy.py 处理）:
      manifest.variables  <  vars_file  <  cli_vars
    """
    args = [sys.executable, str(deploy_py()), f"{DEPLOY_MANIFEST_ARG}={manifest}"]
    if vars_file:
        args.append(f"--vars-file={vars_file}")
    if cli_vars:
        args.extend(f"--{k}={v}" for k, v in cli_vars.items())
    if auto_yes:
        args.append(DEPLOY_AUTO_YES_ARG)
    return subprocess.run(args).returncode
