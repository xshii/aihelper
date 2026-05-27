"""pa-debug CLI。V0 只提供 instrument 子命令。"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import click

from .git_guard import DirtyWorkingTree, ensure_clean
from .l1_transformer.rules_loader import load_aliases, load_blacklist, load_rules
from .l1_transformer.transformer import instrument as _instrument

# 幂等哨兵:已插桩文件头部写这行,再次运行直接拒绝,防重复插桩(覆盖 --allow-dirty / 误提交)。
INSTRUMENTED_MARK = "/* pa-debug:instrumented — 还原用 git checkout */"


@click.group()
def main() -> None:
    """算子调试与对照工具。"""


@main.command()
@click.argument("src", type=click.Path(exists=True))
@click.option("--stub-dir", type=click.Path(exists=True), required=True, help="stub header 目录")
@click.option("--rules-dir", type=click.Path(exists=True), default="./rules", help="规则目录")
@click.option("--meta-dir", type=click.Path(), default="./.pa-debug", help="站点清单输出目录")
@click.option("--allow-dirty", is_flag=True, help="跳过 git 干净检查(不安全)")
def instrument(src: str, stub_dir: str, rules_dir: str, meta_dir: str, allow_dirty: bool) -> None:
    """就地对 SRC 插桩(git 当撤销),站点清单写到 meta-dir。"""
    if INSTRUMENTED_MARK in Path(src).read_text():
        raise click.ClickException(f"{src} 已插桩;先 git checkout {src} 还原后再运行")
    if not allow_dirty:
        try:
            ensure_clean(src)
        except DirtyWorkingTree as e:
            raise click.ClickException(str(e)) from e

    rules = load_rules(rules_dir)
    aliases = load_aliases(rules_dir)
    blacklist = load_blacklist(rules_dir)
    out_c, manifest = _instrument(
        src, rules=rules, clang_args=["-I", stub_dir], aliases=aliases, blacklist=blacklist
    )

    Path(src).write_text(INSTRUMENTED_MARK + "\n" + out_c)
    meta = Path(meta_dir)
    meta.mkdir(parents=True, exist_ok=True)
    # 每个源文件一份清单,避免插桩多个文件时互相覆盖。
    sites_path = meta / f"{Path(src).name}.sites.json"
    sites_path.write_text(json.dumps([asdict(s) for s in manifest], ensure_ascii=False, indent=2))
    click.echo(
        f"instrumented in place: {src} ({len(manifest)} site(s)); "
        f"清单 → {sites_path};还原: git checkout {src}"
    )
