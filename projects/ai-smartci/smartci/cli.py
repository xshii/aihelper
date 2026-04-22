"""smartci CLI 入口（click 命令组）

PURPOSE: 顶层动词 build / smoke + 辅助组 resource / artifact。
PATTERN: click 回调极薄，业务逻辑全部委托给对应 Pipeline / Service 类。
FOR: 团队成员日常调用；弱 AI 写新子命令时模仿这套结构。
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import click

from smartci.artifact.client import default_client
from smartci.const import DEFAULT_LIST_LIMIT
from smartci.packaging.pipeline import BuildPipeline
from smartci.resource_merge.converter import ExcelToXmlConverter
from smartci.resource_merge.merger import XmlMerger
from smartci.resource_merge.validator import XmlValidator
from smartci.smoke.pipeline import SmokePipeline


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


# ── 主流程 ─────────────────────────────────────────────
@cli.command()
@click.option("--team", required=True)
@click.option("--peer", required=True)
@click.option("--peer-version", default="latest")
@click.option("--peer-commit", default=None)
@click.option("--platforms", required=True, help="逗号分隔，如 fpga,emu")
@click.option("--skip-merge", is_flag=True)
@click.option("--no-upload", is_flag=True)
def build(
    team: str, peer: str, peer_version: str, peer_commit: Optional[str],
    platforms: str, skip_merge: bool, no_upload: bool,
) -> None:
    """构建打包阶段（merge + 联合打包 + 上传）"""
    pipeline = BuildPipeline(
        team=team, peer=peer,
        peer_version=peer_version, peer_commit=peer_commit,
        platforms=platforms.split(","),
        skip_merge=skip_merge, no_upload=no_upload,
    )
    raise SystemExit(pipeline.run())


@cli.command()
@click.option("--version", required=True)
@click.option("--commit", required=True)
@click.option("--platform", required=True)
def smoke(version: str, commit: str, platform: str) -> None:
    """冒烟执行阶段（拉合并产物 + 加工 + 跑冒烟）"""
    pipeline = SmokePipeline(version=version, commit=commit, platform=platform)
    raise SystemExit(pipeline.run())


# ── 制品仓 ─────────────────────────────────────────────
@cli.group()
def artifact() -> None:
    """制品仓查询 / 下载（debug 用）"""


@artifact.command(name="list")
@click.option("--team", default=None)
@click.option("--limit", default=DEFAULT_LIST_LIMIT, type=int)
def artifact_list(team: Optional[str], limit: int) -> None:
    """查询制品"""
    for entry in default_client().list(team=team, limit=limit):
        click.echo(entry)


@artifact.command()
@click.option("--name", required=True)
@click.option("--version", required=True)
@click.option("--commit", required=True)
@click.option("--output-dir", default=".")
def pull(name: str, version: str, commit: str, output_dir: str) -> None:
    """下载产物"""
    default_client().pull(
        name=name, version=version, commit=commit, output_dir=Path(output_dir)
    )


if __name__ == "__main__":
    cli()
