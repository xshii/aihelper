"""路径工具：项目根 / config / 工作目录 / deploy.py 定位

PATTERN: 单一入口的纯函数 + 环境变量覆盖；不引入 OS-specific 依赖。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from smartci.const import (
    CONFIG_DIR_NAME,
    DEFAULT_WORKDIR_BASE,
    DEPLOY_PY_FILENAME,
    DEPLOY_PY_RELATIVE,
    ENV_DEPLOY_PY,
    ENV_ROOT,
    ENV_WORKDIR,
    PLATFORMS_DIR_NAME,
    SCRIPTS_DIR_NAME,
)


def project_root() -> Path:
    """ai-smartci 项目根目录（packaging/manifest 所有相对路径的基准）。

    smartci/common/paths.py → ai-smartci/smartci/common/paths.py，所以 parents[2]。
    可通过 SMARTCI_ROOT 环境变量覆盖。
    """
    env = os.environ.get(ENV_ROOT)
    if env:
        return Path(env).resolve()
    # parents[2]: ai-smartci/smartci/common/paths.py → ai-smartci/
    # 独立部署（smartci 不作为包内模块被加载）时用 SMARTCI_ROOT 环境变量覆盖
    return Path(__file__).resolve().parents[2]


def config_dir() -> Path:
    return project_root() / CONFIG_DIR_NAME


def platforms_dir() -> Path:
    """平台自治目录（platforms/{plat}/platform.yaml + package/bundle/smoke 脚本）"""
    return project_root() / PLATFORMS_DIR_NAME


def workdir(run_id: str) -> Path:
    """每次 build/smoke 的临时工作目录（manifest.json + .deploy.state 落地处）。"""
    base = Path(os.environ.get(ENV_WORKDIR, DEFAULT_WORKDIR_BASE))
    return base / run_id


def deploy_py(override: Optional[Path] = None) -> Path:
    """定位 deploy.py。

    优先级:
      1. 参数 override
      2. 环境变量 SMARTCI_DEPLOY_PY
      3. 本仓 scripts/deploy.py（独立部署时；把 deploy.py 拷进来即生效）
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
