"""IO 中枢的 round-trip 验证：Excel ↔ YAML ↔ XML ↔ Excel。"""
from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from ecfg.io.exporters import excel as excel_exporter
from ecfg.io.exporters import xml as xml_exporter
from ecfg.io.exporters.yaml import write_tables as write_yaml_tables
from ecfg.io.importers.excel import excel_to_tables
from ecfg.io.importers.xml import xml_to_tables
from ecfg.io.importers.yaml import read_yaml_dir, read_yaml_file
from ecfg.model import Record, Table


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


@pytest.fixture
def sample_tables() -> list[Table]:
    return [
        Table(
            base_name="Irq",
            records=[
                Record(index={"vector": 10}, attribute={"priority": 2, "trigger": "edge"}),
                Record(index={"vector": 20}, attribute={"priority": 5, "trigger": "level"}),
            ],
            source_hint="memory",
        ),
        Table(
            base_name="Dma",
            records=[
                Record(index={"channelId": 0}, attribute={"size": 1024}),
            ],
        ),
    ]


class TestYamlRoundTrip:
    def test_write_then_read(self, tmp_path: Path, sample_tables: list[Table]):
        out_dir = tmp_path / "tables"
        write_yaml_tables(sample_tables, out_dir)
        read_back = read_yaml_dir(out_dir)
        assert sorted(t.base_name for t in read_back) == ["Dma", "Irq"]
        irq = next(t for t in read_back if t.base_name == "Irq")
        assert irq.records[0].index == {"vector": 10}
        assert irq.records[0].attribute == {"priority": 2, "trigger": "edge"}

    def test_read_single_file(self, tmp_path: Path, sample_tables: list[Table]):
        out_dir = tmp_path / "tables"
        write_yaml_tables(sample_tables, out_dir)
        t = read_yaml_file(out_dir / "Irq.yaml")
        assert t.base_name == "Irq"
        assert len(t.records) == 2


class TestXmlRoundTrip:
    def test_write_then_read(self, tmp_path: Path, sample_tables: list[Table]):
        xml_path = tmp_path / "merged.xml"
        xml_exporter.write_tables(sample_tables, xml_path)
        tables = xml_to_tables(xml_path)
        names = sorted(t.base_name for t in tables)
        assert names == ["Dma", "Irq"]
        irq = next(t for t in tables if t.base_name == "Irq")
        # XML 没有 index/attribute 区分，原 index+attribute 全部进 attribute
        assert irq.records[0].attribute == {
            "vector": 10, "priority": 2, "trigger": "edge",
        }
        assert irq.records[0].index == {}

    def test_list_value_emitted_as_repeated_children(self, tmp_path: Path):
        t = Table(base_name="Cluster", records=[
            Record(
                index={"id": 1},
                attribute={"tables": ["t1", "t2", "t3"]},
            ),
        ])
        xml_path = tmp_path / "out.xml"
        xml_exporter.write_tables([t], xml_path)
        text = xml_path.read_text(encoding="utf-8")
        assert text.count("<tables>") == 3
        # round-trip 读回，list 被还原
        back = xml_to_tables(xml_path)
        assert back[0].records[0].attribute["tables"] == ["t1", "t2", "t3"]

    def test_refuses_overwrite(self, tmp_path: Path, sample_tables):
        xml = tmp_path / "m.xml"
        xml_exporter.write_tables(sample_tables, xml)
        with pytest.raises(FileExistsError):
            xml_exporter.write_tables(sample_tables, xml)
        xml_exporter.write_tables(sample_tables, xml, force=True)

    def test_boolean_coercion(self, tmp_path: Path):
        t = Table(base_name="A", records=[
            Record(index={"id": 1}, attribute={"enabled": True, "name": "foo"}),
        ])
        xml_path = tmp_path / "out.xml"
        xml_exporter.write_tables([t], xml_path)
        back = xml_to_tables(xml_path)
        rec = back[0].records[0]
        assert rec.attribute["enabled"] is True
        assert rec.attribute["name"] == "foo"


class TestExcelRoundTrip:
    def test_write_and_read_back(self, tmp_path: Path, sample_tables: list[Table]):
        xlsx_path = tmp_path / "out.xlsx"
        excel_exporter.write_tables(sample_tables, xlsx_path)

        # 读回：注意 excel_to_tables 只有 index 概念（首列），
        # 所以 index/attribute 分布会不同，但数据该在
        tables = excel_to_tables(xlsx_path)
        assert sorted(t.base_name for t in tables) == ["Dma", "Irq"]
        irq = next(t for t in tables if t.base_name == "Irq")
        # 首列 vector 作为 index
        assert irq.records[0].index == {"vector": 10}
        assert irq.records[0].attribute == {"priority": 2, "trigger": "edge"}

    def test_list_values_joined_with_pipe(self, tmp_path: Path):
        t = Table(base_name="Cluster", records=[
            Record(index={"id": 1}, attribute={"tables": ["t1", "t2"]}),
        ])
        xlsx = tmp_path / "out.xlsx"
        excel_exporter.write_tables([t], xlsx)
        # 读回后 tables 字段会是 "t1|t2" 字符串（attribute）
        tables = excel_to_tables(xlsx)
        rec = tables[0].records[0]
        assert rec.attribute["tables"] == "t1|t2"
