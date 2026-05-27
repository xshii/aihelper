"""判断一个函数调用是否 intrinsic:定义所在头文件归属 + 正则黑白名单。"""

from __future__ import annotations

import re
from pathlib import Path

from .config import DiscoveryConfig


def is_intrinsic(decl_file: str | None, name: str, cfg: DiscoveryConfig) -> bool:
    if decl_file is None:
        return False
    if Path(decl_file).name not in cfg.intrinsic_headers:
        return False
    if any(re.search(pat, name) for pat in cfg.deny):
        return False
    if cfg.allow and not any(re.search(pat, name) for pat in cfg.allow):
        return False
    return True
