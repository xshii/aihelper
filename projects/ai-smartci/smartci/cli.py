"""smartci CLI 入口（click 命令组）

三组命令:
  - resource  资源表 Excel ↔ XML 合并校验（独立业务）
  - bundle    打包流水线（合并 → 平台打包上传）
  - smoke     冒烟流水线（拉产物 → bundle 脚本 → 跑用例）

bundle/smoke 都是 subprocess 调 deploy.py 跑对应 manifest，
smartci 不做 task 编排，只做 CLI 参数到 --key=value 的透传 +
可选附加仓内固化 vars-file（platforms/_shared/vars.json）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import click

from smartci.common.paths import platform_manifest, platforms_dir, shared_manifest
from smartci.const import SHARED_SUBDIR
from smartci.resource_merge.converter import ExcelToXmlConverter
from smartci.resource_merge.merger import XmlMerger
from smartci.resource_merge.validator import XmlValidator
from smartci.runner import run_deploy


SHARED_VARS_FILE = platforms_dir() / SHARED_SUBDIR / "vars.json"


def _shared_vars_file() -> Optional[Path]:
    """返回 platforms/_shared/vars.json 路径（若存在），否则 None。"""
    return SHARED_VARS_FILE if SHARED_VARS_FILE.exists() else None


def _run_with_defaults(manifest: Path, cli_vars: Dict[str, str]) -> int:
    """统一入口：自动带上 _shared/vars.json（如有）+ 透传 CLI 变量。"""
    return run_deploy(manifest, cli_vars=cli_vars, vars_file=_shared_vars_file())


@click.group()
def cli() -> None:
    """smartci - 硬件资源表合并 + 冒烟支撑"""


# ── 资源表 ─────────────────────────────────────────────
@cli.group()
def resource() -> None:
    """资源表：Excel ↔ XML / 合并 / 校验"""


@resource.command()
@click.option("--input", "input_path", required=True, type=click.Path(exists=True))
@click.option("--output", "output_path", required=True, type=click.Path())
@click.option("--team", required=True)
def convert(input_path: str, output_path: str, team: str) -> None:
    """Excel → 团队 XML"""
    ExcelToXmlConverter(team=team).convert(Path(input_path), Path(output_path))


@resource.command()
@click.option("--inputs", multiple=True, required=True, type=click.Path(exists=True))
@click.option("--output", "output_path", required=True, type=click.Path())
def merge(inputs: List[str], output_path: str) -> None:
    """多团队 XML → 最终 XML"""
    XmlMerger().merge([Path(p) for p in inputs], Path(output_path))


@resource.command()
@click.option("--input", "input_path", required=True, type=click.Path(exists=True))
def validate(input_path: str) -> None:
    """校验 XML（结构 + 语义）"""
    XmlValidator().validate(Path(input_path))


# ── 打包流水线 ─────────────────────────────────────────
@cli.command()
@click.option("--platform", required=True)
@click.option("--team", required=True)
@click.option("--peer", required=True)
@click.option("--peer-version", default="latest")
@click.option("--peer-commit", default=None)
@click.option("--skip-merge", is_flag=True,
              help="跳过公共 merge stage（resources/final.xml 已就绪时用）")
def bundle(
    platform: str, team: str, peer: str,
    peer_version: str, peer_commit: Optional[str], skip_merge: bool,
) -> None:
    """打包流水线：合并资源表（可选）→ 平台 bundle（拉对方产物 + 打包 + 上传）"""
    cli_vars: Dict[str, str] = {
        "platform": platform, "team": team,
        "peer": peer, "peer_version": peer_version,
    }
    if peer_commit:
        cli_vars["peer_commit"] = peer_commit

    if not skip_merge:
        rc = _run_with_defaults(shared_manifest("merge"), cli_vars)
        if rc != 0:
            raise SystemExit(rc)

    raise SystemExit(_run_with_defaults(platform_manifest(platform, "bundle"), cli_vars))


# ── 冒烟流水线 ─────────────────────────────────────────
@cli.command()
@click.option("--platform", required=True)
@click.option("--version", required=True)
@click.option("--commit", required=True)
@click.option("--commit-short", default=None,
              help="短 commit（默认取 --commit 前 8 位）")
def smoke(
    platform: str, version: str, commit: str, commit_short: Optional[str],
) -> None:
    """冒烟流水线：拉合并产物 → bundle 脚本 → 跑冒烟入口"""
    cli_vars: Dict[str, str] = {
        "platform": platform, "version": version, "commit": commit,
        "commit_short": commit_short or commit[:8],
    }
    raise SystemExit(_run_with_defaults(platform_manifest(platform, "smoke"), cli_vars))


if __name__ == "__main__":
    cli()
