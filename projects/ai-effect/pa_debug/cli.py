"""pa-debug CLI。V0 只提供 instrument 子命令。"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import click

from .l1_transformer.rules_loader import load_aliases, load_blacklist, load_rules
from .l1_transformer.transformer import instrument as _instrument


@click.group()
def main() -> None:
    """算子调试与对照工具。"""


@main.command()
@click.argument("src", type=click.Path(exists=True))
@click.option("--stub-dir", type=click.Path(exists=True), required=True, help="stub header 目录")
@click.option("--rules-dir", type=click.Path(exists=True), default="./rules", help="规则目录")
@click.option("--out-dir", type=click.Path(), default="./out", help="输出目录")
def instrument(src: str, stub_dir: str, rules_dir: str, out_dir: str) -> None:
    """对 SRC 插桩,输出插桩后 .c 与 sites.json。"""
    rules = load_rules(rules_dir)
    aliases = load_aliases(rules_dir)
    blacklist = load_blacklist(rules_dir)
    out_c, manifest = _instrument(
        src, rules=rules, clang_args=["-I", stub_dir], aliases=aliases, blacklist=blacklist
    )
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    dst = out_path / Path(src).name
    dst.write_text(out_c)
    sites = [asdict(s) for s in manifest]
    (out_path / "sites.json").write_text(json.dumps(sites, ensure_ascii=False, indent=2))
    click.echo(f"instrumented → {dst}  ({len(manifest)} site(s))")
