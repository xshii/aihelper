"""加载外置规则目录:扫描 *.py,收集模块级 RULE / RULES,返回 Rule 列表。

框架不携带任何项目专属规则;规则实例住在项目的 rules/ 目录,运行时动态加载。
弱 AI 新增一种宏,只需往 rules/ 丢一个声明文件(定义 RULE = Rule(...)),不改框架代码。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from .rule import Blacklist, Rule


def _load_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"_pa_rule_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载规则文件: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rules_from_module(module: ModuleType) -> list[Rule]:
    found: list[Rule] = []
    single = getattr(module, "RULE", None)
    if isinstance(single, Rule):
        found.append(single)
    multiple = getattr(module, "RULES", None)
    if isinstance(multiple, list):
        found.extend(r for r in multiple if isinstance(r, Rule))
    return found


def load_rules(rules_dir: str | Path) -> list[Rule]:
    root = Path(rules_dir)
    if not root.is_dir():
        raise NotADirectoryError(f"规则目录不存在: {root}")
    collected: list[Rule] = []
    for path in sorted(root.rglob("*.py")):
        if path.name.startswith("_"):
            continue
        collected.extend(_rules_from_module(_load_module(path)))
    return collected


def load_aliases(rules_dir: str | Path) -> dict[str, str]:
    """从 rules/isomorphisms.py 读 ALIASES(别名宏 → 规范宏)。文件不存在则返回空。"""
    path = Path(rules_dir) / "isomorphisms.py"
    if not path.is_file():
        return {}
    aliases = getattr(_load_module(path), "ALIASES", None)
    return dict(aliases) if isinstance(aliases, dict) else {}


def load_blacklist(rules_dir: str | Path) -> Blacklist:
    """从 rules/blacklist.py 读 SKIP_FILES / SKIP_FUNCTIONS。文件不存在则返回空黑名单。"""
    path = Path(rules_dir) / "blacklist.py"
    if not path.is_file():
        return Blacklist()
    module = _load_module(path)
    return Blacklist(
        skip_files=list(getattr(module, "SKIP_FILES", []) or []),
        skip_functions=list(getattr(module, "SKIP_FUNCTIONS", []) or []),
    )
