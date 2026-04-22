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

from smartci.common.paths import config_dir
from smartci.const import (
    ARTIFACT_REPO_YAML,
    DEFAULT_ARTIFACT_TOOL,
    PLATFORMS_SUBDIR,
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
    """直接保留 post_process / smoke_entry 的原始 dict 列表，
    渲染 manifest 时透传给 deploy.py（避免重复 schema 设计）。"""
    platform: str
    packager: str
    post_process: List[Dict[str, Any]] = field(default_factory=list)
    smoke_entry: Dict[str, Any] = field(default_factory=dict)
    output: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, platform: str, root: Optional[Path] = None) -> "PlatformConfig":
        path = (root or config_dir()) / PLATFORMS_SUBDIR / f"{platform}.yaml"
        raw = _load_yaml(path)
        return cls(
            platform=raw["platform"],
            packager=raw["packager"],
            post_process=raw.get("post_process", []),
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
