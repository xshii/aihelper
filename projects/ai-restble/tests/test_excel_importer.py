from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook
from ruamel.yaml import YAML

from ecfg.io.exporters.yaml import write_tables
from ecfg.io.importers.excel import (
    excel_to_tables,
    to_camel_case,
    to_pascal_case,
)


def _make_xlsx(path: Path, sheets: dict[str, list[list]]) -> None:
    wb = Workbook()
    default = wb.active
    if default is not None:
        wb.remove(default)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title=title)
        for r in rows:
            ws.append(r)
    wb.save(path)


def _load_yaml(path: Path):
    yaml = YAML()
    with path.open("r", encoding="utf-8") as f:
        return yaml.load(f)


class TestNameNormalization:
    def test_pascal_from_space(self):
        assert to_pascal_case("irq table") == "IrqTable"

    def test_pascal_from_underscore(self):
        assert to_pascal_case("IRQ_TABLE") == "IrqTable"

    def test_pascal_preserves_camel(self):
        assert to_pascal_case("irqTbl") == "IrqTbl"

    def test_pascal_from_dash(self):
        assert to_pascal_case("dma-channel") == "DmaChannel"

    def test_camel_basic(self):
        assert to_camel_case("core id") == "coreId"
        assert to_camel_case("CoreId") == "coreId"
        assert to_camel_case("core_id") == "coreId"


class TestExcelToTables:
    def test_basic_first_col_as_index(self, tmp_path: Path):
        xlsx = tmp_path / "src.xlsx"
        _make_xlsx(xlsx, {
            "Irq Table": [
                ["vector", "priority", "trigger", "enabled"],
                [10, 2, "edge", True],
                [20, 5, "level", False],
            ],
        })
        tables = excel_to_tables(xlsx)
        assert len(tables) == 1
        t = tables[0]
        assert t.base_name == "IrqTable"
        assert len(t.records) == 2
        assert t.records[0].index == {"vector": 10}
        assert t.records[0].attribute == {
            "priority": 2, "trigger": "edge", "enabled": True,
        }
        assert t.records[0].ref == {}

    def test_composite_index_override(self, tmp_path: Path):
        xlsx = tmp_path / "src.xlsx"
        _make_xlsx(xlsx, {
            "PinMux": [
                ["bank", "number", "moduleType", "altFunction"],
                ["A", 0, "uart", "AF1"],
            ],
        })
        tables = excel_to_tables(
            xlsx, index_overrides={"PinMux": ["bank", "number", "moduleType"]},
        )
        rec = tables[0].records[0]
        assert rec.index == {"bank": "A", "number": 0, "moduleType": "uart"}
        assert rec.attribute == {"altFunction": "AF1"}

    def test_skip_fully_empty_rows(self, tmp_path: Path):
        xlsx = tmp_path / "src.xlsx"
        _make_xlsx(xlsx, {
            "Simple": [
                ["id", "name"],
                [1, "a"],
                [None, None],
                [2, "b"],
            ],
        })
        tables = excel_to_tables(xlsx)
        assert len(tables[0].records) == 2

    def test_multiple_sheets(self, tmp_path: Path):
        xlsx = tmp_path / "src.xlsx"
        _make_xlsx(xlsx, {
            "IrqTbl": [["vector", "priority"], [10, 2]],
            "DmaTbl": [["channelId", "size"], [0, 1024]],
        })
        tables = excel_to_tables(xlsx)
        assert sorted(t.base_name for t in tables) == ["DmaTbl", "IrqTbl"]

    def test_header_empty_raises(self, tmp_path: Path):
        xlsx = tmp_path / "src.xlsx"
        _make_xlsx(xlsx, {
            "A": [["id", None, "name"], [1, "x", "y"]],
        })
        with pytest.raises(ValueError, match="表头为空"):
            excel_to_tables(xlsx)

    def test_index_override_missing_col_raises(self, tmp_path: Path):
        xlsx = tmp_path / "src.xlsx"
        _make_xlsx(xlsx, {
            "A": [["id", "name"], [1, "x"]],
        })
        with pytest.raises(ValueError, match="找不到 index 列"):
            excel_to_tables(xlsx, index_overrides={"A": ["nope"]})

    def test_sheet_with_only_header_skipped(self, tmp_path: Path):
        xlsx = tmp_path / "src.xlsx"
        _make_xlsx(xlsx, {
            "Empty": [["id", "name"]],
            "WithData": [["id", "name"], [1, "x"]],
        })
        tables = excel_to_tables(xlsx)
        assert [t.base_name for t in tables] == ["WithData"]


class TestWriteTablesYaml:
    def test_header_comment_and_content(self, tmp_path: Path):
        xlsx = tmp_path / "src.xlsx"
        _make_xlsx(xlsx, {
            "Irq": [["vector", "priority"], [10, 2]],
        })
        tables = excel_to_tables(xlsx)
        results = write_tables(tables, tmp_path / "tables")
        assert len(results) == 1
        r = results[0]
        assert r.base_name == "Irq"
        assert r.row_count == 1
        text = r.output_path.read_text(encoding="utf-8")
        assert "# Irq.yaml" in text
        assert "从 src.xlsx 自动生成" in text
        data = _load_yaml(r.output_path)
        assert data[0]["index"] == {"vector": 10}
        assert data[0]["attribute"] == {"priority": 2}

    def test_refuses_overwrite_without_force(self, tmp_path: Path):
        xlsx = tmp_path / "src.xlsx"
        _make_xlsx(xlsx, {
            "A": [["id", "name"], [1, "x"]],
        })
        tables = excel_to_tables(xlsx)
        write_tables(tables, tmp_path / "tables")
        with pytest.raises(FileExistsError):
            write_tables(tables, tmp_path / "tables")
        write_tables(tables, tmp_path / "tables", force=True)
