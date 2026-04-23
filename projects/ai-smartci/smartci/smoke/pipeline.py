"""SmokePipeline - 冒烟执行阶段编排

PATTERN: 加载 PlatformConfig → SmokeManifestAssembler 装配 → DeployRunner 执行
FOR: cli.smoke 直接实例化调用。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from smartci.common.config_loader import PlatformConfig
from smartci.common.paths import project_root, workdir
from smartci.const import RUN_ID_SMOKE_PREFIX
from smartci.manifest_render import SmokeManifestAssembler
from smartci.runner import DeployRunner


@dataclass
class SmokePipeline:
    version: str
    commit: str
    platform: str
    runner: DeployRunner = field(default_factory=DeployRunner)

    def run(self) -> int:
        plat_cfg = PlatformConfig.load(self.platform)
        manifest = SmokeManifestAssembler(
            version=self.version, commit=self.commit, platform=self.platform,
            bundle=list(plat_cfg.bundle),
            smoke_entry=dict(plat_cfg.smoke_entry),
        ).assemble()
        return self.runner.run(
            manifest=manifest,
            workdir=workdir(self._run_id()),
            exec_cwd=project_root(),
        )

    def _run_id(self) -> str:
        return f"{RUN_ID_SMOKE_PREFIX}{self.platform}-{self.version}-{self.commit}"
