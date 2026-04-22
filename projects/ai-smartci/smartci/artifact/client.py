"""制品仓 client - ABC + 命令行工具实现坑位 + 默认工厂

PATTERN: ABC 定义三个核心操作（upload/pull/list），具体实现按工具不同切换子类。
         default_client() 从 config/artifact_repo.yaml 构造，业务代码无需关心配置细节。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from smartci.common.config_loader import ArtifactRepoConfig
from smartci.const import DEFAULT_ARTIFACT_TOOL  # noqa: F401  (导出给外部用)


@dataclass(frozen=True)
class ArtifactEntry:
    name: str
    version: str
    commit: str
    size_bytes: int
    uploaded_at: str
    built_by: Optional[str] = None


class ArtifactClient(ABC):
    @abstractmethod
    def upload(self, file_path: Path) -> None: ...

    @abstractmethod
    def pull(
        self, name: str, version: str, commit: str, output_dir: Path,
    ) -> Path: ...

    @abstractmethod
    def list(
        self, team: Optional[str] = None, limit: int = 10,
    ) -> List[ArtifactEntry]: ...


@dataclass
class CliArtifactClient(ArtifactClient):
    """封装已有二进制工具的 client — 坑位；子类/直接实现时填入 tool 的具体命令"""

    endpoint: str
    namespace: str
    tool: str                 # 已有 CLI 的可执行名
    auth: dict

    def upload(self, file_path: Path) -> None:
        raise NotImplementedError(
            f"CliArtifactClient.upload 待对接 {self.tool}（upload {file_path}）"
        )

    def pull(
        self, name: str, version: str, commit: str, output_dir: Path,
    ) -> Path:
        raise NotImplementedError(
            f"CliArtifactClient.pull 待对接 {self.tool}"
            f"（{name}-{version}-{commit} → {output_dir}）"
        )

    def list(
        self, team: Optional[str] = None, limit: int = 10,
    ) -> List[ArtifactEntry]:
        raise NotImplementedError(
            f"CliArtifactClient.list 待对接 {self.tool}（team={team}, limit={limit}）"
        )


def default_client() -> ArtifactClient:
    """从 config/artifact_repo.yaml 构建默认 client。"""
    cfg = ArtifactRepoConfig.load()
    return CliArtifactClient(
        endpoint=cfg.endpoint,
        namespace=cfg.namespace,
        tool=cfg.tool,
        auth=dict(cfg.auth),
    )
