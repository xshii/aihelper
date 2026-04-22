"""manifest_render 的 Assembler 输出结构测试

只测 dict 输出结构，不跑 deploy.py。
"""

from __future__ import annotations
from smartci.manifest_render import (
    BuildManifestAssembler,
    ManifestBuilder,
    SmokeManifestAssembler,
)


def test_manifest_builder_fluent_interface():
    m = (
        ManifestBuilder()
        .var("k", "v")
        .task("t1", "echo 1", order=1)
        .task("t2", "echo 2", order=2, keyword=[{"type": "success", "word": "ok"}])
        .build()
    )
    assert m["variables"] == {"k": "v"}
    assert len(m["tasks"]) == 2
    assert m["tasks"][1]["keyword"] == [{"type": "success", "word": "ok"}]


def test_build_manifest_includes_merge_by_default():
    manifest = BuildManifestAssembler(
        team="team-a", peer="team-b", peer_version="latest",
        platforms=["fpga", "emu"],
    ).assemble()
    names = [t["name"] for t in manifest["tasks"]]
    assert "merge-resource" in names
    assert "package-fpga" in names and "package-emu" in names
    assert "upload" in names


def test_build_manifest_skip_merge_and_no_upload():
    manifest = BuildManifestAssembler(
        team="team-a", peer="team-b", peer_version="latest",
        platforms=["fpga"], skip_merge=True, no_upload=True,
    ).assemble()
    names = [t["name"] for t in manifest["tasks"]]
    assert "merge-resource" not in names
    assert "upload" not in names


def test_build_manifest_parallel_platforms_share_order():
    manifest = BuildManifestAssembler(
        team="team-a", peer="team-b", peer_version="latest",
        platforms=["fpga", "emu"],
    ).assemble()
    pkg_tasks = [t for t in manifest["tasks"] if t["name"].startswith("package-")]
    # 两个平台打包任务 order 相同 → deploy.py 自动并行
    assert len({t["order"] for t in pkg_tasks}) == 1


def test_smoke_manifest_threads_platform_config():
    post_process = [
        {"name": "remap", "usage": "scripts/x.sh",
         "keyword": [{"type": "success", "word": "done"}]},
    ]
    smoke_entry = {"usage": "scripts/run.sh", "keyword": [{"type": "error", "word": "F"}]}
    manifest = SmokeManifestAssembler(
        version="v1", commit="abc", platform="fpga",
        post_process=post_process, smoke_entry=smoke_entry,
    ).assemble()
    names = [t["name"] for t in manifest["tasks"]]
    # 必含 pull/extract/remap（透传 post_process）/smoke-run
    assert names[0] == "pull" and names[1] == "extract"
    assert "remap" in names
    assert names[-1] == "smoke-run"
    # smoke_entry 透传了 keyword
    smoke_task = manifest["tasks"][-1]
    assert smoke_task["keyword"] == [{"type": "error", "word": "F"}]
