"""IntermediateArtifact - 平台无关的联合打包中间产物

PATTERN: frozen dataclass，所有团队产物 + 合并资源表 + 版本信息。
        平台 packager 接这个对象，不关心原始路径的来源。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class TeamArtifactSet:
    """一个团队的产物集合（按类型分目录）"""
    team_id: str
    root: Path                      # 该团队产物解压/就位目录
    binaries: Dict[str, Path] = field(default_factory=dict)  # type → path


@dataclass(frozen=True)
class IntermediateArtifact:
    """平台无关中间产物。

    - 多个团队产物按 team_id 索引
    - 合并后的 final.xml 独立字段
    - version/commit 用于最终命名（取"最晚上传"的团队产物）
    """
    teams: Dict[str, TeamArtifactSet]
    resource_xml: Path
    version: str
    commit_short: str
    sources: Dict[str, Dict[str, str]] = field(default_factory=dict)
    resource_version: Optional[Dict[str, str]] = None

    @property
    def team_ids(self) -> list:
        return sorted(self.teams)
