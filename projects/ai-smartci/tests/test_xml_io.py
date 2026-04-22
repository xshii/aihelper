"""XmlMerger 的 lxml 读写 + 跨表触发合并的端到端测试

用 team-a.xml / team-b.xml 两份 fixture 跑完整 merge 流程，验证:
  - _parse_inputs 能按 selector_xpath + fields + children_xpaths 抽出 ResourceItem
  - cluster 融合触发 table 跨团队合并（UNION_AS_NEW）
  - count_field 在融合后被移除
  - _write_output 产出结构化 XML 文件
"""

from __future__ import annotations

from lxml import etree

from smartci.resource_merge.merger import XmlMerger
from smartci.resource_merge.strategies._cluster_example import (
    ClusterStrategy,
    TableStrategy,
)
from smartci.resource_merge.strategies.registry import StrategyRegistry


def _isolated_registry() -> StrategyRegistry:
    """给 XmlMerger 一个只含 cluster / table 的隔离 registry（不受全局注册干扰）"""
    reg = StrategyRegistry()
    reg.register(ClusterStrategy)
    reg.register(TableStrategy)
    return reg


def test_parse_cluster_and_tables(fixture_dir):
    merger = XmlMerger(registry=_isolated_registry())
    parsed = merger._parse_inputs([fixture_dir / "team-a.xml"])

    # cluster 的 children_xpaths 抽出 tables list
    cluster_items = parsed["cluster"]["team-a"]
    assert len(cluster_items) == 1
    cl = cluster_items[0]
    assert cl.attrs["type"] == "cpu_cluster"
    assert cl.attrs["number"] == "2"
    assert cl.list_attrs["tables"] == ["tbl_a_irq", "tbl_a_mem"]

    # table 有 2 张（a 的 irq + mem）
    table_items = parsed["table"]["team-a"]
    names = sorted(it.attrs["name"] for it in table_items)
    assert names == ["tbl_a_irq", "tbl_a_mem"]


def test_end_to_end_merge_with_trigger(fixture_dir, tmp_path):
    """完整跑：cluster 融合 → tables 并集 → 触发 table 跨表合并（UNION_AS_NEW）"""
    merger = XmlMerger(registry=_isolated_registry())
    out = tmp_path / "final.xml"
    report = merger.merge(
        [fixture_dir / "team-a.xml", fixture_dir / "team-b.xml"], out,
    )

    # ── cluster 层：融合后 tables 并集 ────
    clusters = report.merged_by_type["cluster"]
    assert len(clusters) == 1
    cl = clusters[0]
    assert cl.is_merged
    # 融合后 number 应该被移除
    assert "number" not in cl.attrs
    # tables 并集
    assert set(cl.list_attrs["tables"]) == {"tbl_a_irq", "tbl_a_mem", "tbl_b_irq"}

    # ── table 层：UNION_AS_NEW 把 tbl_a_irq + tbl_a_mem + tbl_b_irq 合成一张 ────
    tables = report.merged_by_type["table"]
    # 融合后只有一张表（unified name = "tbl_a_irq+tbl_a_mem+tbl_b_irq"）
    assert len(tables) == 1
    unified = tables[0]
    assert unified.is_merged
    assert "+" in unified.attrs["name"]
    # count 被移除
    assert "count" not in unified.attrs

    # ── 输出文件存在且可解析 ────
    assert out.exists()
    tree = etree.parse(str(out))
    root = tree.getroot()
    assert root.tag == "merged"
    rt_tags = {child.tag for child in root}
    assert "cluster" in rt_tags and "table" in rt_tags


def test_parse_empty_team_returns_empty_lists(tmp_path, fixture_dir):
    """没有 cluster / table 的 XML 应返回空列表，不抛异常"""
    empty = tmp_path / "empty.xml"
    empty.write_text('<?xml version="1.0"?><hardware></hardware>', encoding="utf-8")
    merger = XmlMerger(registry=_isolated_registry())
    parsed = merger._parse_inputs([empty])
    assert parsed["cluster"]["empty"] == []
    assert parsed["table"]["empty"] == []
