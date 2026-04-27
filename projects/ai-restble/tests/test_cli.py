from __future__ import annotations

from click.testing import CliRunner

from ecfg.cli import main


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    for cmd in ("validate", "expand", "serve", "import-excel"):
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
    assert data["phase"] == 0
    assert data["config"].endswith("fake-config.yaml")


def test_app_index():
    from ecfg.app import create_app

    app = create_app("demo.yaml")
    client = app.test_client()
    r = client.get("/")
    assert r.status_code == 200
    assert b"ecfg" in r.data
    assert b"demo.yaml" in r.data


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
