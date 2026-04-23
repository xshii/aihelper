"""YAML 配置 → dataclass 加载器

PATTERN: 每类配置一个 frozen dataclass + classmethod load()，加载时校验关键字段。
        加载失败立即抛 FileNotFoundError / KeyError，不返回 None。
FOR: pipeline / packager / artifact_client 消费已校验过的强类型对象。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from smartci.common.paths import config_dir, platforms_dir
from smartci.const import (
    ARTIFACT_REPO_YAML,
    DEFAULT_ARTIFACT_TOOL,
    PLATFORM_YAML,
    TEAMS_SUBDIR,
)


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@dataclass(frozen=True)
class BinarySpec:
    path: str
    type: str


@dataclass(frozen=True)
class TeamConfig:
    team_id: str
    repo_root: str
    binaries: List[BinarySpec]
    version_file: str
    commit_source: str
    excel_path: str
    xml_path: str

    @classmethod
    def load(cls, team_id: str, root: Optional[Path] = None) -> "TeamConfig":
        path = (root or config_dir()) / TEAMS_SUBDIR / f"{team_id}.yaml"
        raw = _load_yaml(path)
        artifacts = raw["artifacts"]
        rt = raw["resource_table"]
        return cls(
            team_id=raw["team_id"],
            repo_root=raw["repo_root"],
            binaries=[BinarySpec(**b) for b in artifacts["binaries"]],
            version_file=artifacts["metadata"]["version_file"],
            commit_source=artifacts["metadata"]["commit_source"],
            excel_path=rt["excel"],
            xml_path=rt["xml"],
        )


@dataclass(frozen=True)
class PlatformConfig:
    """平台配置（加载自 platforms/{platform}/platform.yaml）。

    原始 dict 列表（package_entry / bundle / smoke_entry）直接透传给 deploy.py，
    避免重复 schema 设计。
    """
    platform: str
    packager: str
    package_entry: Dict[str, Any] = field(default_factory=dict)      # 脚本打包入口
    bundle: List[Dict[str, Any]] = field(default_factory=list)    # bundle（冒烟前镜像组装）
    smoke_entry: Dict[str, Any] = field(default_factory=dict)        # 冒烟入口
    output: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(
        cls, platform: str, root: Optional[Path] = None,
    ) -> "PlatformConfig":
        """默认从 platforms/{platform}/platform.yaml 加载；root 指向 platforms/ 父目录。

        传 root 时等价 root / "platforms" / platform / "platform.yaml"（用于测试隔离）。
        """
        base = (root / "platforms") if root else platforms_dir()
        path = base / platform / PLATFORM_YAML
        raw = _load_yaml(path)
        return cls(
            platform=raw["platform"],
            packager=raw.get("packager", ""),
            package_entry=raw.get("package_entry", {}),
            bundle=raw.get("bundle", []),
            smoke_entry=raw.get("smoke_entry", {}),
            output=raw.get("output", {}),
        )


@dataclass(frozen=True)
class ArtifactRepoConfig:
    endpoint: str
    namespace: str
    tool: str
    auth: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Optional[Path] = None) -> "ArtifactRepoConfig":
        path = (root or config_dir()) / ARTIFACT_REPO_YAML
        raw = _load_yaml(path)
        return cls(
            endpoint=raw["endpoint"],
            namespace=raw["namespace"],
            tool=raw.get("tool", DEFAULT_ARTIFACT_TOOL),
            auth=raw.get("auth", {}),
        )
