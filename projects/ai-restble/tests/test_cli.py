from __future__ import annotations

from click.testing import CliRunner

from ecfg.cli import main


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    for cmd in (
        "validate", "expand", "serve",
        "import-excel", "import-xml", "export-xml", "export-excel",
        "unpack", "pack", "scaffold",
    ):
        assert cmd in result.output


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "ecfg" in result.output


def test_app_health():
    from ecfg.app import create_app

    app = create_app("/tmp/fake-config.yaml")
    client = app.test_client()
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"
    assert data["phase"] == 2
    assert data["config"].endswith("fake-config.yaml")


def test_app_index():
    from ecfg.app import create_app

    app = create_app("demo.yaml")
    client = app.test_client()
    r = client.get("/")
    assert r.status_code == 200
    assert b"ai-restble" in r.data
    assert b"echarts" in r.data  # ECharts CDN 引用必在页内


def test_import_excel_rejects_bad_index_spec(tmp_path):
    runner = CliRunner()
    xlsx = tmp_path / "x.xlsx"
    xlsx.write_bytes(b"not a real xlsx")
    result = runner.invoke(
        main,
        ["import-excel", str(xlsx), "--index-col", "bad-no-colon"],
    )
    assert result.exit_code != 0
    assert "SHEET:col" in result.output


def test_unpack_pack_cli_round_trip(tmp_path):
    """``ecfg unpack`` + ``ecfg pack`` round-trip 字节级一致 (CLI 路径)."""
    from pathlib import Path

    fixture_xml = Path(__file__).parent / "fixtures" / "xml" / "valid" / "minimal.xml"
    runner = CliRunner()

    out_dir = tmp_path / "tree"
    r1 = runner.invoke(main, ["unpack", str(fixture_xml), str(out_dir)])
    assert r1.exit_code == 0, r1.output
    assert (out_dir / "FileInfo.yaml").is_file()
    assert (out_dir / "template" / "_children_order.yaml").is_file()

    out_xml = tmp_path / "round.xml"
    r2 = runner.invoke(main, ["pack", str(out_dir), "-o", str(out_xml)])
    assert r2.exit_code == 0, r2.output
    assert out_xml.read_text() == fixture_xml.read_text()


def test_pack_cli_refuses_overwrite_without_force(tmp_path):
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "xml" / "valid" / "minimal.expected"
    out_xml = tmp_path / "x.xml"
    out_xml.write_text("existing", encoding="utf-8")
    runner = CliRunner()
    r = runner.invoke(main, ["pack", str(fixture), "-o", str(out_xml)])
    assert r.exit_code != 0
    assert "已存在" in r.output


def test_scaffold_cli_generates_template(tmp_path):
    from pathlib import Path

    fixture_xml = (
        Path(__file__).parent / "fixtures" / "xml" / "valid" / "multi_runmode.xml"
    )
    runner = CliRunner()
    r = runner.invoke(
        main, ["scaffold", str(fixture_xml), "-o", str(tmp_path / "out")],
    )
    assert r.exit_code == 0, r.output
    tmpl = tmp_path / "out" / "template"
    assert (tmpl / "shared" / "FileInfo.yaml").is_file()
    assert (tmpl / "0x00000000" / "RunModeTbl.yaml").is_file()
