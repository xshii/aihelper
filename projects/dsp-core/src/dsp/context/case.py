"""用例管理 — 目录结构 + seed。

用例目录: {脚本名}_{时间戳}_s{seed}/
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger("dsp.context")


def make_case_dir(data_path: str, seed: int) -> str:
    """generate_input: 创建 {脚本名}_{时间戳}_s{seed}/ 子目录。"""
    import inspect
    from datetime import datetime

    frame = inspect.stack()[-1]
    script_name = Path(frame.filename).stem

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    case_dir = Path(data_path) / f"{script_name}_{timestamp}_s{seed}"
    case_dir.mkdir(parents=True, exist_ok=True)
    return str(case_dir)


def resolve_case_dir_and_seed(data_path: str, seed: int) -> tuple[str, int]:
    """use_input: 找到要加载的用例目录，从目录名提取 seed。"""
    base = Path(data_path)
    if not base.exists():
        return data_path, seed

    chosen = data_path
    if not is_case_dir(base):
        case_dirs = sorted(
            [d for d in base.iterdir() if d.is_dir() and is_case_dir(d)],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
        if case_dirs:
            chosen = str(case_dirs[0])
            logger.info("自动选择最新用例: %s", chosen)

    m = re.search(r"_s(\d+)$", Path(chosen).name)
    if m:
        seed = int(m.group(1))

    return chosen, seed


def is_case_dir(d: Path) -> bool:
    """判断目录是否是用例目录（含策略子目录 + .txt）。"""
    from ..data.datagen import DEFAULT_STRATEGIES
    strategy_names = {s.name for s in DEFAULT_STRATEGIES}
    for child in d.iterdir():
        if child.is_dir() and child.name in strategy_names:
            if any(child.glob("*.txt")):
                return True
    return False
