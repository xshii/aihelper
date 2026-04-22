"""artifact.naming 命名规则"""

from __future__ import annotations
from smartci.artifact.naming import JointPackageName, TeamPackageName


def test_joint_package_name_str():
    n = JointPackageName(platform="fpga", version="v1.2.3", commit_short="a4f9d0")
    assert str(n) == "hw-fpga-v1.2.3-a4f9d0"
    assert n.with_ext("tar.gz") == "hw-fpga-v1.2.3-a4f9d0.tar.gz"


def test_joint_package_name_custom_product():
    n = JointPackageName(
        platform="emu", version="v2", commit_short="c0ffee", product="soc",
    )
    assert str(n) == "soc-emu-v2-c0ffee"


def test_team_package_name_str():
    n = TeamPackageName(team="team-a", version="v1", commit_short="abc")
    assert str(n) == "team-a-v1-abc"
    assert n.with_ext() == "team-a-v1-abc.tar.gz"
