"""路径工具：项目根 / 平台目录 / deploy.py 定位 / manifest helper

PATTERN: 纯函数 + 环境变量覆盖。不依赖任何 OS-specific。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from smartci.const import (
    DEPLOY_PY_FILENAME,
    DEPLOY_PY_RELATIVE,
    ENV_DEPLOY_PY,
    ENV_ROOT,
    PLATFORMS_DIR_NAME,
    SCRIPTS_DIR_NAME,
    SHARED_SUBDIR,
)


def project_root() -> Path:
    """ai-smartci 项目根目录。

    parents[2]: ai-smartci/smartci/common/paths.py → ai-smartci/
    非 monorepo 部署时通过 SMARTCI_ROOT 环境变量覆盖。
    """
    env = os.environ.get(ENV_ROOT)
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[2]


def platforms_dir() -> Path:
    """平台自治目录（platforms/{plat}/{bundle,smoke}.manifest.json + 脚本）"""
    return project_root() / PLATFORMS_DIR_NAME


def platform_manifest(platform: str, stage: str) -> Path:
    """platforms/{platform}/{stage}.manifest.json"""
    return platforms_dir() / platform / f"{stage}.manifest.json"


def shared_manifest(name: str) -> Path:
    """platforms/_shared/{name}.manifest.json（跨平台公共流程）"""
    return platforms_dir() / SHARED_SUBDIR / f"{name}.manifest.json"


def deploy_py(override: Optional[Path] = None) -> Path:
    """定位 deploy.py。

    优先级:
      1. 参数 override
      2. 环境变量 SMARTCI_DEPLOY_PY
      3. 本仓 scripts/deploy.py（独立部署时）
      4. fallback: monorepo 同级 ../dsp-integration/deploy.py（开发便利）
    """
    if override:
        return Path(override).resolve()
    env = os.environ.get(ENV_DEPLOY_PY)
    if env:
        return Path(env).resolve()
    bundled = project_root() / SCRIPTS_DIR_NAME / DEPLOY_PY_FILENAME
    if bundled.exists():
        return bundled
    return project_root().parent / DEPLOY_PY_RELATIVE
