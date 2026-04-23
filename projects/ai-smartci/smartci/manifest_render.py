"""ManifestBuilder + 各阶段 Assembler - 把配置/参数渲染成 deploy.py 的 manifest dict

PATTERN:
  - ManifestBuilder：fluent builder，链式 .var().task().raw_task() 累积
  - BuildManifestAssembler / SmokeManifestAssembler：把业务参数翻成 task 列表
  - Assembler 接受**扁平字段**（不依赖 config_loader 的类）—— 保证单向依赖
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class ManifestBuilder:
    """链式累积 variables / tasks，build() 出 dict。"""

    def __init__(self) -> None:
        self._variables: Dict[str, str] = {}
        self._tasks: List[Dict[str, Any]] = []

    def var(self, key: str, value: str) -> "ManifestBuilder":
        self._variables[key] = value
        return self

    def task(
        self,
        name: str,
        usage: str,
        order: int,
        keyword: Optional[List[Dict[str, Any]]] = None,
    ) -> "ManifestBuilder":
        t: Dict[str, Any] = {"name": name, "order": order, "usage": usage}
        if keyword:
            t["keyword"] = list(keyword)
        self._tasks.append(t)
        return self

    def raw_task(self, task: Dict[str, Any]) -> "ManifestBuilder":
        """直接塞 task dict（platform yaml 的 bundle 透传场景）。"""
        self._tasks.append(dict(task))
        return self

    def build(self) -> Dict[str, Any]:
        return {"variables": dict(self._variables), "tasks": list(self._tasks)}


@dataclass
class BuildManifestAssembler:
    """构建打包阶段的 manifest 装配器。"""

    team: str
    peer: str
    peer_version: str
    platforms: List[str]
    skip_merge: bool = False
    no_upload: bool = False
    peer_commit: Optional[str] = None

    def assemble(self) -> Dict[str, Any]:
        b = (
            ManifestBuilder()
            .var("team", self.team).var("peer", self.peer)
            .var("peer_version", self.peer_version)
        )
        if self.peer_commit:
            b.var("peer_commit", self.peer_commit)

        order = 1
        if not self.skip_merge:
            b.task(
                "merge-resource", order=order,
                usage=(
                    "python -m smartci resource merge "
                    "--inputs resources/team-a.xml resources/team-b.xml "
                    "--output resources/final.xml"
                ),
            )
            order += 1

        b.task(
            "fetch-peer", order=order,
            usage="echo 'TODO: artifact-cli pull ${peer}-${peer_version}*'",
        )
        order += 1

        for plat in self.platforms:  # 同 order → 并行
            b.task(
                f"package-{plat}", order=order,
                usage=f"echo 'TODO: build {plat} 联合包'",
            )
        order += 1

        if not self.no_upload:
            b.task("upload", order=order, usage="echo 'TODO: artifact-cli push'")

        return b.build()


@dataclass
class SmokeManifestAssembler:
    """冒烟执行阶段的 manifest 装配器。

    接受扁平字段（不依赖 PlatformConfig 等上层类），保持单向依赖：
      bundle / smoke_entry 由 SmokePipeline 从 yaml 配置解构后传入。
    """

    version: str
    commit: str
    platform: str
    bundle: List[Dict[str, Any]] = field(default_factory=list)
    smoke_entry: Dict[str, Any] = field(default_factory=dict)
    workdir_template: str = "/tmp/smartci-work/${version}-${commit}"

    def assemble(self) -> Dict[str, Any]:
        b = (
            ManifestBuilder()
            .var("version", self.version)
            .var("commit", self.commit)
            .var("platform", self.platform)
            .var("pkg_dir", self.workdir_template)
            .var("report_path", f"{self.workdir_template}/report.json")
        )

        order = 1
        b.task(
            "pull", order=order,
            usage=(
                "echo 'TODO: artifact-cli pull "
                "hw-${platform}-${version}-${commit}.tar.gz -o ${pkg_dir}'"
            ),
            keyword=[{"type": "success", "word": "downloaded"}],
        )
        order += 1
        b.task(
            "extract", order=order,
            usage=(
                "mkdir -p ${pkg_dir}/work && "
                "echo 'TODO: tar xzf ${pkg_dir}/*.tar.gz -C ${pkg_dir}/work'"
            ),
        )
        order += 1

        for step in self.bundle:
            b.raw_task({**step, "order": order})
            order += 1

        if self.smoke_entry:
            b.raw_task({"name": "smoke-run", "order": order, **self.smoke_entry})

        return b.build()
