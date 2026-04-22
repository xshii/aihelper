"""config_loader 的 dataclass 加载（用 fixture yaml）"""

from __future__ import annotations
from smartci.common.config_loader import PlatformConfig, TeamConfig


def test_load_team_config(fixture_dir):
    cfg = TeamConfig.load("test-team", root=fixture_dir)
    assert cfg.team_id == "test-team"
    assert len(cfg.binaries) == 1
    assert cfg.binaries[0].type == "elf"
    assert cfg.version_file == "build/output/VERSION"
    assert cfg.xml_path == "resources/test-team.xml"


def test_load_platform_config(fixture_dir):
    cfg = PlatformConfig.load("test-plat", root=fixture_dir)
    assert cfg.platform == "test-plat"
    assert cfg.packager == "TestPackager"
    assert len(cfg.post_process) == 1
    assert cfg.post_process[0]["name"] == "demo_step"
    assert cfg.smoke_entry["usage"].startswith("scripts/test/run.sh")
