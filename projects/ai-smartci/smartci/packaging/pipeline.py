"""BuildPipeline - 构建打包阶段编排

PATTERN: Pipeline 类封装一次 build 的状态与步骤。run() 把参数渲染成 manifest，
        交给 DeployRunner → deploy.py 执行。
FOR: cli.build 直接实例化调用。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

from smartci.common.paths import project_root, workdir
from smartci.const import RUN_ID_BUILD_PREFIX, TIMESTAMP_FORMAT
from smartci.manifest_render import BuildManifestAssembler
from smartci.runner import DeployRunner


@dataclass
class BuildPipeline:
    team: str
    peer: str
    peer_version: str
    platforms: List[str]
    skip_merge: bool = False
    no_upload: bool = False
    peer_commit: Optional[str] = None
    runner: DeployRunner = field(default_factory=DeployRunner)

    def run(self) -> int:
        manifest = BuildManifestAssembler(
            team=self.team, peer=self.peer,
            peer_version=self.peer_version, peer_commit=self.peer_commit,
            platforms=self.platforms,
            skip_merge=self.skip_merge, no_upload=self.no_upload,
        ).assemble()
        return self.runner.run(
            manifest=manifest,
            workdir=workdir(self._run_id()),
            exec_cwd=project_root(),
        )

    def _run_id(self) -> str:
        return f"{RUN_ID_BUILD_PREFIX}{self.team}-{time.strftime(TIMESTAMP_FORMAT)}"
