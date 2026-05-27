"""git 守卫:committed=干净通过,modified/untracked/non-repo 三种脏态均拦截。"""

import subprocess
from pathlib import Path

import pytest

from pa_debug.git_guard import DirtyWorkingTree, ensure_clean

pytestmark = pytest.mark.integration


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True)


def _commit(path: Path, name: str, text: str) -> Path:
    f = path / name
    f.write_text(text)
    subprocess.run(["git", "add", name], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=path, check=True)
    return f


def test_committed_file_passes(tmp_path):
    f = _commit(_repo(tmp_path), "a.c", "int x;\n")
    ensure_clean(str(f))  # no raise


def test_modified_file_raises(tmp_path):
    f = _commit(_repo(tmp_path), "a.c", "int x;\n")
    f.write_text("int x; int y;\n")
    with pytest.raises(DirtyWorkingTree):
        ensure_clean(str(f))


def test_untracked_file_raises(tmp_path):
    repo = _repo(tmp_path)
    f = repo / "a.c"
    f.write_text("int x;\n")
    with pytest.raises(DirtyWorkingTree):
        ensure_clean(str(f))


def test_non_repo_raises(tmp_path):
    f = tmp_path / "a.c"
    f.write_text("int x;\n")
    with pytest.raises(DirtyWorkingTree):
        ensure_clean(str(f))


def _repo(path: Path) -> Path:
    _init_repo(path)
    return path
