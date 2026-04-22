"""FPGA 平台打包器（坑位）"""

from __future__ import annotations
from pathlib import Path
from typing import Any

from smartci.packaging.intermediate import IntermediateArtifact
from smartci.packaging.packager.base import PlatformPackager
from smartci.packaging.packager.registry import register_packager


@register_packager
class FpgaPackager(PlatformPackager):
    platform = "fpga"

    def build_package_content(self, intermediate: IntermediateArtifact) -> Any:
        """TODO: fpga 特定打包逻辑（bit 文件、配置、资源表 → 某临时目录）。

        输入：IntermediateArtifact（已按团队子目录组织的内存结构）
        输出：代表包内容的对象（路径 / dict / dataclass），交给 finalize() 封装
        """
        raise NotImplementedError(
            f"FpgaPackager.build_package_content 待实现 "
            f"(teams={intermediate.team_ids}, version={intermediate.version})"
        )

    def finalize(self, content: Any, output_dir: Path) -> Path:
        """TODO: 打成 hw-fpga-<version>-<commit>.tar.gz，附 manifest.json"""
        raise NotImplementedError("FpgaPackager.finalize 待实现（tar.gz + manifest.json）")
