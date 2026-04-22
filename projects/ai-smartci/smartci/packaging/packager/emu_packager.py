"""emu 平台打包器（坑位）"""

from __future__ import annotations
from pathlib import Path
from typing import Any

from smartci.packaging.intermediate import IntermediateArtifact
from smartci.packaging.packager.base import PlatformPackager
from smartci.packaging.packager.registry import register_packager


@register_packager
class EmuPackager(PlatformPackager):
    platform = "emu"

    def build_package_content(self, intermediate: IntermediateArtifact) -> Any:
        raise NotImplementedError(
            f"EmuPackager.build_package_content 待实现 "
            f"(teams={intermediate.team_ids}, version={intermediate.version})"
        )

    def finalize(self, content: Any, output_dir: Path) -> Path:
        raise NotImplementedError("EmuPackager.finalize 待实现（tar.gz + manifest.json）")
