"""DeployRunner - 把渲染好的 manifest 委托给 dsp-integration/deploy.py

PURPOSE: smartci 不重新发明流水线调度。流水线引擎复用 deploy.py。
PATTERN: 类封装 (deploy_py 路径 + 默认 -y)，run() 接收 manifest dict + workdir，
         返回 deploy.py 的退出码。
FOR: packaging.pipeline / smoke.pipeline 的最终一步。
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from smartci.common.paths import deploy_py as default_deploy_py
from smartci.const import (
    DEPLOY_AUTO_YES_ARG,
    DEPLOY_MANIFEST_ARG,
    DEPLOY_MANIFEST_FILENAME,
)


@dataclass
class DeployRunner:
    deploy_py: Path = None  # type: ignore[assignment]  # __post_init__ 兜底
    auto_yes: bool = True

    def __post_init__(self) -> None:
        if self.deploy_py is None:
            self.deploy_py = default_deploy_py()

    def run(self, manifest: dict, workdir: Path, exec_cwd: Optional[Path] = None) -> int:
        """渲染 manifest.json 到 workdir，subprocess 调起 deploy.py。

        - workdir：manifest.json 落地处，deploy.py 的 .deploy.state 也跟随它
        - exec_cwd：deploy.py 的工作目录（task 里相对路径的基准），默认调用者 cwd
        """
        workdir.mkdir(parents=True, exist_ok=True)
        manifest_path = self._write_manifest(manifest, workdir)
        return self._exec(manifest_path, exec_cwd or Path.cwd())

    def _write_manifest(self, manifest: dict, workdir: Path) -> Path:
        path = workdir / DEPLOY_MANIFEST_FILENAME
        path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return path

    def _exec(self, manifest_path: Path, cwd: Path) -> int:
        args = [
            sys.executable, str(self.deploy_py),
            f"{DEPLOY_MANIFEST_ARG}={manifest_path}",
        ]
        if self.auto_yes:
            args.append(DEPLOY_AUTO_YES_ARG)
        return subprocess.run(args, cwd=str(cwd)).returncode
