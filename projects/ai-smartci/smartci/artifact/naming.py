"""版本命名规则 — frozen dataclass，__str__ 给出文件名字符串

两类产物:
  - 联合产物：hw-{platform}-{version}-{commit_short}.{ext}
  - 团队产物：{team}-{version}-{commit_short}.{ext}
"""
from __future__ import annotations

from dataclasses import dataclass

from smartci.const import PKG_EXT_DEFAULT, PRODUCT_DEFAULT


@dataclass(frozen=True)
class JointPackageName:
    """联合产物命名"""
    platform: str
    version: str
    commit_short: str
    product: str = PRODUCT_DEFAULT

    def __str__(self) -> str:
        return f"{self.product}-{self.platform}-{self.version}-{self.commit_short}"

    def with_ext(self, ext: str = PKG_EXT_DEFAULT) -> str:
        return f"{self}.{ext}"


@dataclass(frozen=True)
class TeamPackageName:
    """团队产物命名（供对方 build 时拉取）"""
    team: str
    version: str
    commit_short: str

    def __str__(self) -> str:
        return f"{self.team}-{self.version}-{self.commit_short}"

    def with_ext(self, ext: str = PKG_EXT_DEFAULT) -> str:
        return f"{self}.{ext}"
