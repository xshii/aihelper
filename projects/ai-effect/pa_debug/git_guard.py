"""git 工作树守卫:就地插桩前确认目标文件干净(git 当撤销的前提)。

就地插桩会改写源码,用 git 作为撤销手段(git checkout 还原)。前提是被插桩的文件已提交、
工作树干净;否则插桩产物会和开发者未提交的改动混在一起,无法干净还原。
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class DirtyWorkingTree(Exception):
    """目标文件有未提交改动 / 未被跟踪 / 不在 git 仓库 —— 就地插桩不安全。"""


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def ensure_clean(path: str) -> None:
    """目标文件在 git 仓库内且无未提交改动则通过;否则抛 DirtyWorkingTree。"""
    target = Path(path).resolve()
    cwd = target.parent
    inside = _git(["rev-parse", "--is-inside-work-tree"], cwd)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        raise DirtyWorkingTree(f"{path} 不在 git 仓库内;就地插桩需要 git 作为撤销手段")
    status = _git(["status", "--porcelain", "--", str(target)], cwd)
    if status.stdout.strip():
        raise DirtyWorkingTree(
            f"{path} 有未提交改动或未被跟踪;请先 git commit/stash,或加 --allow-dirty 跳过"
        )
