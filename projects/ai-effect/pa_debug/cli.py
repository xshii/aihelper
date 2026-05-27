"""pa-debug CLI。instrument(第一级调用)/ instrument-macros(第二级硬件宏)。

两者都就地改写 + git 守卫 + 幂等 marker;关闭 pa_dump_enabled 时近零开销,可常驻。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import click

from .git_guard import DirtyWorkingTree, ensure_clean
from .l1_transformer.config import DiscoveryConfig
from .l1_transformer.model import Site
from .l1_transformer.transformer import instrument as _instrument
from .l1_transformer.transformer import instrument_macros as _instrument_macros

# 幂等哨兵:已插桩文件头部写这行,再次运行直接拒绝,防重复插桩(覆盖 --allow-dirty / 误提交)。
INSTRUMENTED_MARK = "/* pa-debug:instrumented — 还原用 git checkout */"


def _precheck(src: str, allow_dirty: bool) -> None:
    if INSTRUMENTED_MARK in Path(src).read_text():
        raise click.ClickException(f"{src} 已插桩;先 git checkout {src} 还原后再运行")
    if not allow_dirty:
        try:
            ensure_clean(src)
        except DirtyWorkingTree as e:
            raise click.ClickException(str(e)) from e


def _finish(src: str, meta_dir: str, out_c: str, manifest: list[Site]) -> None:
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


@click.group()
def main() -> None:
    """算子调试与对照工具。"""


@main.command()
@click.argument("src", type=click.Path(exists=True))
@click.option(
    "-I",
    "--include",
    "includes",
    multiple=True,
    type=click.Path(exists=True),
    help="clang include 目录",
)
@click.option(
    "--intrinsic-header",
    "intrinsic_headers",
    multiple=True,
    required=True,
    help="算 intrinsic 的头文件名",
)
@click.option("--allow", multiple=True, help="名字白名单(正则)")
@click.option("--deny", multiple=True, help="名字黑名单(正则)")
@click.option("--print-fn", default="printf", help="dump 用的 printf 风格函数名")
@click.option("--meta-dir", type=click.Path(), default="./.pa-debug", help="站点清单输出目录")
@click.option("--allow-dirty", is_flag=True, help="跳过 git 干净检查(不安全)")
def instrument(
    src: str,
    includes: tuple[str, ...],
    intrinsic_headers: tuple[str, ...],
    allow: tuple[str, ...],
    deny: tuple[str, ...],
    print_fn: str,
    meta_dir: str,
    allow_dirty: bool,
) -> None:
    """第一级:就地对用户 SRC 的 intrinsic 调用点插桩。"""
    _precheck(src, allow_dirty)
    cfg = DiscoveryConfig(
        intrinsic_headers=list(intrinsic_headers),
        allow=list(allow),
        deny=list(deny),
        print_fn=print_fn,
    )
    clang_args = [arg for inc in includes for arg in ("-I", str(inc))]
    out_c, manifest = _instrument(src, cfg, clang_args=clang_args)
    _finish(src, meta_dir, out_c, manifest)


@main.command(name="instrument-macros")
@click.argument("src", type=click.Path(exists=True))
@click.option(
    "-I",
    "--include",
    "includes",
    multiple=True,
    type=click.Path(exists=True),
    help="clang include 目录",
)
@click.option("--macro", "macros", multiple=True, required=True, help="硬件宏名(可多次)")
@click.option("--print-fn", default="printf", help="dump 用的 printf 风格函数名")
@click.option("--meta-dir", type=click.Path(), default="./.pa-debug", help="站点清单输出目录")
@click.option("--allow-dirty", is_flag=True, help="跳过 git 干净检查(不安全)")
def instrument_macros(
    src: str,
    includes: tuple[str, ...],
    macros: tuple[str, ...],
    print_fn: str,
    meta_dir: str,
    allow_dirty: bool,
) -> None:
    """第二级:就地对头文件 SRC 里 inline 体内的硬件宏插桩。"""
    _precheck(src, allow_dirty)
    cfg = DiscoveryConfig(
        intrinsic_headers=[],
        hardware_macros=list(macros),
        print_fn=print_fn,
    )
    clang_args = [arg for inc in includes for arg in ("-I", str(inc))]
    out_c, manifest = _instrument_macros(src, cfg, clang_args=clang_args)
    _finish(src, meta_dir, out_c, manifest)
