"""PlatformPackager - 平台打包器基类（模板方法模式）

PATTERN:
  package() = 模板方法，定义 pre → build_content → post → finalize 四步
  子类必须实现 build_package_content()，其余三步可选覆盖
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

from smartci.packaging.intermediate import IntermediateArtifact


class PlatformPackager(ABC):
    platform: ClassVar[str] = ""  # 子类必须覆盖

    def package(self, intermediate: IntermediateArtifact, output_dir: Path) -> Path:
        """模板方法：统一四步流程。返回最终包文件路径。"""
        self.pre_package(intermediate)
        content = self.build_package_content(intermediate)
        self.post_package(content)
        return self.finalize(content, output_dir)

    @abstractmethod
    def build_package_content(self, intermediate: IntermediateArtifact) -> Any:
        """平台特定打包逻辑：返回一个代表包内容的对象（路径 / dataclass / dict 均可）。"""

    def pre_package(self, intermediate: IntermediateArtifact) -> None:
        """可选钩子：校验 / 环境准备"""

    def post_package(self, content: Any) -> None:
        """可选钩子：内容写完后、打 tar 前的收尾"""

    def finalize(self, content: Any, output_dir: Path) -> Path:
        """打 tar.gz 的默认实现 — 坑位。子类可自定义（如 bit 镜像直接返回）。"""
        raise NotImplementedError(
            f"{self.__class__.__name__}.finalize 默认实现未就位（TODO: tar.gz）"
        )
