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
    DEPLOY_PY_RELATIVE,
    ENV_DEPLOY_PY,
    ENV_ROOT,
    ENV_WORKDIR,
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


def workdir(run_id: str) -> Path:
    """每次 build/smoke 的临时工作目录（manifest.json + .deploy.state 落地处）。"""
    base = Path(os.environ.get(ENV_WORKDIR, DEFAULT_WORKDIR_BASE))
    return base / run_id


def deploy_py(override: Optional[Path] = None) -> Path:
    """定位 dsp-integration/deploy.py。

    优先级：参数 > SMARTCI_DEPLOY_PY 环境变量 > 同级仓库 ../dsp-integration/deploy.py
    """
    if override:
        return Path(override).resolve()
    env = os.environ.get(ENV_DEPLOY_PY)
    if env:
        return Path(env).resolve()
    return project_root().parent / DEPLOY_PY_RELATIVE
