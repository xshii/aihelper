"""ecfg 命令行入口（click group）。业务逻辑均由 lazy import 的工人模块承担。"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Tuple

import click

from ecfg import __version__

if TYPE_CHECKING:
    from ecfg.io.exporters.yaml import WriteResult


@click.group()
@click.version_option(__version__, prog_name="ecfg")
def main() -> None:
    """ecfg — YAML-first 嵌入式资源表工具。"""


@main.command()
@click.argument("config", type=click.Path(), required=False, default="config.yaml")
def validate(config: str) -> None:
    """(Phase 1 stub) 校验 include / index / ref / 聚合 / schema。"""
    click.echo(f"[stub] validate {config}")


@main.command()
@click.argument("config", type=click.Path(), required=False, default="config.yaml")
def expand(config: str) -> None:
    """(Phase 1 stub) 展开所有 include，输出合并后的 YAML。"""
    click.echo(f"[stub] expand {config}")


@main.command()
@click.argument("config", type=click.Path(), required=False, default="config.yaml")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", type=int, default=5000, show_default=True)
@click.option("--debug/--no-debug", default=True)
def serve(config: str, host: str, port: int, debug: bool) -> None:
    """启动 Flask 画布（Phase 0：占位页）。"""
    from ecfg.app import create_app

    app = create_app(config)
    click.echo(f"[ecfg] 占位页 http://{host}:{port}  (config: {config})")
    app.run(host=host, port=port, debug=debug)


# region import-* ──────────────────────────────────────────────────────────
@main.command("import-excel")
@click.argument("xlsx_file", type=click.Path(exists=True, dir_okay=False))
@click.option("-o", "--output-dir", type=click.Path(file_okay=False),
              default="tables", show_default=True,
              help="输出目录，每个 sheet 生成一个 <BaseName>.yaml")
@click.option("--index-col", "index_specs", multiple=True,
              metavar="SHEET:col[,col2,...]",
              help="指定某张表的 index 列（可重复）。未指定时默认使用第一列。")
@click.option("--force/--no-force", default=False,
              help="覆盖已存在的 yaml 文件。")
def import_excel(xlsx_file: str, output_dir: str,
                 index_specs: Tuple[str, ...], force: bool) -> None:
    """Excel → YAML tables。首列默认作 index，--index-col 覆盖。"""
    from ecfg.io.exporters.yaml import write_tables
    from ecfg.io.importers.excel import excel_to_tables

    overrides = _parse_index_specs(index_specs)
    tables = excel_to_tables(Path(xlsx_file), index_overrides=overrides)
    results = write_tables(tables, Path(output_dir), force=force)
    _report_write(results, output_dir)


@main.command("import-xml")
@click.argument("xml_file", type=click.Path(exists=True, dir_okay=False))
@click.option("-o", "--output-dir", type=click.Path(file_okay=False),
              default="tables", show_default=True)
@click.option("--force/--no-force", default=False)
def import_xml(xml_file: str, output_dir: str, force: bool) -> None:
    """XML → YAML tables。所有字段进 attribute；index 需后续补。"""
    from ecfg.io.exporters.yaml import write_tables
    from ecfg.io.importers.xml import xml_to_tables

    tables = xml_to_tables(Path(xml_file))
    results = write_tables(tables, Path(output_dir), force=force)
    _report_write(results, output_dir)


# endregion

# region export-* ──────────────────────────────────────────────────────────
@main.command("export-xml")
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False))
@click.option("-o", "--output", type=click.Path(dir_okay=False),
              default="merged.xml", show_default=True)
@click.option("--force/--no-force", default=False)
def export_xml(input_dir: str, output: str, force: bool) -> None:
    """YAML tables → 单份 XML（硬件下游格式）。"""
    from ecfg.io.exporters import xml as xml_exporter
    from ecfg.io.importers.yaml import read_yaml_dir

    tables = read_yaml_dir(Path(input_dir))
    path = xml_exporter.write_tables(tables, Path(output), force=force)
    click.echo(f"{len(tables)} 张表 → {path}")


@main.command("export-excel")
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False))
@click.option("-o", "--output", type=click.Path(dir_okay=False),
              default="out.xlsx", show_default=True)
@click.option("--force/--no-force", default=False)
def export_excel(input_dir: str, output: str, force: bool) -> None:
    """YAML tables → 单份 Excel，每张表一个 sheet。"""
    from ecfg.io.exporters import excel as excel_exporter
    from ecfg.io.importers.yaml import read_yaml_dir

    tables = read_yaml_dir(Path(input_dir))
    path = excel_exporter.write_tables(tables, Path(output), force=force)
    click.echo(f"{len(tables)} 张表 → {path}")


# endregion

# region legacy XML round-trip ─────────────────────────────────────────────
@main.command("unpack")
@click.argument("xml_files", type=click.Path(exists=True, dir_okay=False), nargs=-1,
                required=True)
@click.argument("output_dir", type=click.Path(file_okay=False))
def unpack_cmd(xml_files: Tuple[str, ...], output_dir: str) -> None:
    """Legacy XML → YAML 文件树（拆解到 OUTPUT_DIR/）；多 XML 幂等去重合一."""
    from ecfg.legacy.preprocess import unpack_many

    unpack_many([Path(f) for f in xml_files], Path(output_dir))
    click.echo(f"unpack: {len(xml_files)} XML(s) → {output_dir}/")


@main.command("pack")
@click.argument("fixture_dir", type=click.Path(exists=True, file_okay=False))
@click.option("-o", "--output", type=click.Path(dir_okay=False), required=True,
              help="输出 XML 文件路径")
@click.option("--force/--no-force", default=False)
def pack_cmd(fixture_dir: str, output: str, force: bool) -> None:
    """YAML 文件树 → legacy XML（字节级稳定）."""
    from ecfg.legacy.postprocess import pack

    out_path = Path(output)
    if out_path.exists() and not force:
        raise click.ClickException(f"{out_path} 已存在；用 --force 覆盖")
    out_path.write_text(pack(Path(fixture_dir)), encoding="utf-8")
    click.echo(f"pack: {fixture_dir}/ → {output}")


@main.command("scaffold")
@click.argument("xml_files", type=click.Path(exists=True, dir_okay=False), nargs=-1,
                required=True)
@click.option("-o", "--output-dir", type=click.Path(file_okay=False), required=True,
              help="输出根目录；scaffold 写到 OUTPUT_DIR/template/ 下")
def scaffold_cmd(xml_files: Tuple[str, ...], output_dir: str) -> None:
    """从 XML 生成 template/<scope>/<Element>.yaml schema scaffold（无约束注解）."""
    from ecfg.legacy.scaffold import generate_scaffolds

    generate_scaffolds([Path(f) for f in xml_files], Path(output_dir))
    click.echo(f"scaffold: {len(xml_files)} XML(s) → {output_dir}/template/")


# endregion

# region helpers ───────────────────────────────────────────────────────────
def _parse_index_specs(specs: Tuple[str, ...]) -> Dict[str, List[str]]:
    """把 ``("Sheet:col1,col2", ...)`` 解析成 ``{"Sheet": [col1, col2]}``。"""
    overrides: Dict[str, List[str]] = {}
    for spec in specs:
        if ":" not in spec:
            raise click.BadParameter(
                f"--index-col 需要 SHEET:col[,col2] 格式，收到: {spec!r}"
            )
        sheet, cols = spec.split(":", 1)
        sheet = sheet.strip()
        col_list = [c.strip() for c in cols.split(",") if c.strip()]
        if not sheet or not col_list:
            raise click.BadParameter(f"--index-col 参数为空: {spec!r}")
        overrides[sheet] = col_list
    return overrides


def _report_write(results: List[WriteResult], output_dir: str) -> None:
    """把 YAML 落盘结果摘要打到 stdout。"""
    if not results:
        click.echo("（没有可输出的表）")
        return
    for r in results:
        click.echo(f"  {r.base_name}: {r.row_count} 条记录 → {r.output_path}")
    click.echo(f"\n完成：{len(results)} 张表，输出到 {output_dir}/")


# endregion


if __name__ == "__main__":
    main()
