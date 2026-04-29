"""Phase 2A graph builder 测试 — yaml 目录 → ECharts-friendly JSON 投影协议."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ecfg.viz import build_graph

FIXTURES = Path(__file__).parent / "fixtures" / "xml" / "valid"


# region helpers ────────────────────────────────────────────────────────────
def _by_id(nodes, node_id):
    matches = [n for n in nodes if n["id"] == node_id]
    assert len(matches) == 1, f"node {node_id!r} not found uniquely; got {len(matches)}"
    return matches[0]


# endregion

# region structure shape ────────────────────────────────────────────────────
class TestGraphShape:
    def test_minimal_fixture_basic_shape(self):
        g = build_graph(FIXTURES / "minimal.expected")
        assert set(g.keys()) == {"meta", "nodes", "edges", "referenced_by"}
        assert g["meta"]["yaml_dir"].endswith("minimal.expected")
        assert g["meta"]["node_count"] == len(g["nodes"])
        assert g["meta"]["edge_count"] == len(g["edges"])
        assert g["edges"] == []
        assert g["referenced_by"] == {}

    def test_minimal_fixture_has_root_category_only(self):
        g = build_graph(FIXTURES / "minimal.expected")
        assert g["meta"]["categories"] == ["root"]
        for n in g["nodes"]:
            assert n["category"] == "root"
            assert n["scope"] == "root"

    def test_multi_runmode_has_multiple_scopes(self):
        g = build_graph(FIXTURES / "multi_runmode.expected")
        cats = g["meta"]["categories"]
        assert "shared" in cats
        assert "0x10000000" in cats
        assert "0x20000000" in cats
        # category 顺序按目录 rglob 字典序首次出现
        assert len(cats) == len(set(cats)), "categories 必须去重"


# endregion

# region node fields ────────────────────────────────────────────────────────
class TestNodeFields:
    def test_fileinfo_node_kind(self):
        g = build_graph(FIXTURES / "minimal.expected")
        n = _by_id(g["nodes"], "FileInfo")
        assert n["kind"] == "FileInfo"
        assert n["element"] == "FileInfo"

    def test_wrapper_node_records_and_wrapper_type(self):
        g = build_graph(FIXTURES / "minimal.expected")
        n = _by_id(g["nodes"], "FooTbl")
        assert n["kind"] == "Table"
        assert n["element"] == "ResTbl"
        assert n["wrapper_type"] == "FooTbl"
        assert n["records_preview"] == len(n["records"])
        assert n["records_preview"] >= 1

    def test_records_have_three_region_shape(self):
        g = build_graph(FIXTURES / "minimal.expected")
        n = _by_id(g["nodes"], "FooTbl")
        for r in n["records"]:
            assert set(r.keys()) == {"index", "attribute", "ref"}
            # legacy 数据全进 attribute
            assert r["index"] == {}
            assert r["ref"] == {}
            assert r["attribute"]  # 非空

    def test_field_set_ordered_union(self):
        g = build_graph(FIXTURES / "empty_table.expected")
        # BarTbl 有 1 条 record {Id, Value} → 字段顺序 = 出现序
        n = _by_id(g["nodes"], "BarTbl")
        names = [f["name"] for f in n["fields"]]
        assert names == ["Id", "Value"]
        assert all(f["region"] == "attribute" for f in n["fields"])

    def test_empty_wrapper_zero_records(self):
        g = build_graph(FIXTURES / "empty_table.expected")
        # FooTbl 是 LineNum=0 的空 wrapper（仅 count 锚，无 inner records）
        n = _by_id(g["nodes"], "FooTbl")
        assert n["records_preview"] == 0
        assert n["records"] == []
        assert n["fields"] == []
        # count anchor 不进 table_attributes（保持节点视觉简洁）
        assert "LineNum" not in n["table_attributes"]


# endregion

# region scoped nodes ──────────────────────────────────────────────────────
class TestScopedNodes:
    def test_scoped_node_id_prefixed_with_scope(self):
        g = build_graph(FIXTURES / "multi_runmode.expected")
        ids = {n["id"] for n in g["nodes"]}
        assert "shared/DmaCfgTbl" in ids
        assert "0x10000000/RunModeTbl" in ids
        # FileInfo 在 shared/ 下也走这套
        assert "shared/FileInfo" in ids

    def test_capacity_multi_instance_flat_records(self):
        g = build_graph(FIXTURES / "multi_runmode.expected")
        # shared/CapacityRunModeMapTbl.yaml = wrapper @element:ResTbl + LineNum + inner records
        n = _by_id(g["nodes"], "shared/CapacityRunModeMapTbl")
        assert n["records_preview"] == 2
        # 字段集应有序 union 自所有 record
        names = [f["name"] for f in n["fields"]]
        assert "ChipType" in names
        assert "CapacityID" in names
        assert "RunModeValue" in names

    def test_self_named_scoped_table_attributes_separated(self):
        g = build_graph(FIXTURES / "multi_runmode.expected")
        n = _by_id(g["nodes"], "0x10000000/RunModeTbl")
        # RunModeTbl 顶层有 RunModeDesc/RunMode/ResAllocMode 标量 + ResTblNum 列表锚
        # records 应来自 inner ResTblNum list
        assert n["records_preview"] >= 1
        # 顶层标量进 table_attributes
        assert "RunModeDesc" in n["table_attributes"]
        assert "RunMode" in n["table_attributes"]


# endregion

# region invariants ─────────────────────────────────────────────────────────
class TestInvariants:
    def test_idempotent_same_input_same_output(self):
        g1 = build_graph(FIXTURES / "multi_runmode.expected")
        g2 = build_graph(FIXTURES / "multi_runmode.expected")
        assert json.dumps(g1, sort_keys=True) == json.dumps(g2, sort_keys=True)

    def test_output_is_json_serializable(self):
        g = build_graph(FIXTURES / "multi_runmode.expected")
        # 任何 ruamel 残留都会让 json.dumps 抛 TypeError
        json.dumps(g)

    def test_template_subtree_excluded(self):
        g = build_graph(FIXTURES / "multi_runmode.expected")
        for n in g["nodes"]:
            assert "template" not in n["id"], f"template 子树不应进 graph: {n['id']}"

    def test_children_order_yaml_excluded(self):
        # _children_order.yaml 在 template/ 下，已被 _walk_yamls 排除
        g = build_graph(FIXTURES / "multi_runmode.expected")
        for n in g["nodes"]:
            assert "_children_order" not in n["id"]

    def test_missing_dir_raises(self):
        with pytest.raises(ValueError, match="目录不存在"):
            build_graph(FIXTURES / "nonexistent.fixture")


# endregion

# region template constraints — Phase 2A 联动 template ─────────────────────
class TestTemplateConstraints:
    """``template/<scope>/<E>.yaml`` 的字段注解（@merge / @range / @enum）应嵌入
    到 graph JSON 的 ``node.fields[i].constraints``，前端按此分派 widget."""

    def test_enum_constraint_embedded(self):
        g = build_graph(FIXTURES / "multi_runmode.expected")
        n = _by_id(g["nodes"], "shared/DmaCfgTbl")
        src_type = next(f for f in n["fields"] if f["name"] == "SrcType")
        assert src_type["constraints"]["enum"] == ["MEM", "DEV", "AXI"]

    def test_range_constraint_embedded(self):
        g = build_graph(FIXTURES / "multi_runmode.expected")
        n = _by_id(g["nodes"], "shared/DmaCfgTbl")
        burst = next(f for f in n["fields"] if f["name"] == "BurstSize")
        # 故意 tighten 到 1-8 让现有数据 BurstSize=16 触发异常（demo）
        assert burst["constraints"]["range"] == [1.0, 8.0]

    def test_merge_constraint_embedded(self):
        g = build_graph(FIXTURES / "multi_runmode.expected")
        n = _by_id(g["nodes"], "shared/DmaCfgTbl")
        chan = next(f for f in n["fields"] if f["name"] == "ChannelId")
        assert chan["constraints"]["merge"] == "conflict"

    def test_field_without_template_annotation_has_no_constraints_key(self):
        g = build_graph(FIXTURES / "minimal.expected")
        # minimal fixture template 无注解 → fields[i] 不应有 constraints 键
        n = _by_id(g["nodes"], "FooTbl")
        for f in n["fields"]:
            assert "constraints" not in f

    def test_template_missing_falls_back_silently(self):
        # multi_runmode 中 ClkCfgTbl_0x20000000.yaml 的 bare 是 ClkCfgTbl —
        # template 在 0x00000000/ClkCfgTbl.yaml 但当前无注解 → 退化为无 constraints
        g = build_graph(FIXTURES / "multi_runmode.expected")
        n = _by_id(g["nodes"], "0x20000000/ClkCfgTbl_0x20000000")
        for f in n["fields"]:
            assert "constraints" not in f


# endregion

# region validation — record 值 vs template 约束 ──────────────────────────
class TestValidation:
    """record 值违 ``@enum`` / ``@range`` 时挂 ``record.errors`` + ``node.error_count``."""

    def test_range_violation_flagged(self):
        # multi_runmode 的 DmaCfgTbl 数据 BurstSize=16，template 紧到 1-8 → 1 处异常
        g = build_graph(FIXTURES / "multi_runmode.expected")
        n = _by_id(g["nodes"], "shared/DmaCfgTbl")
        assert n["error_count"] == 1
        rec = n["records"][0]
        assert "errors" in rec
        err = rec["errors"][0]
        assert err["field"] == "BurstSize"
        assert err["kind"] == "range_violation"
        assert "16" in err["message"]

    def test_enum_violation_flagged(self):
        g = build_graph(FIXTURES / "multi_runmode.expected")
        n = _by_id(g["nodes"], "shared/CapacityRunModeMapTbl")
        # ChipType 数据 10/10，template enum 1/2/3 → 2 records 各违规 ChipType
        # 加上 CoreNum/Frequency 等其他 tighten，error_count > 2
        assert n["error_count"] >= 2
        # 第一条 record 必有 ChipType 违规
        first = n["records"][0]
        assert "errors" in first
        kinds = {e["field"]: e["kind"] for e in first["errors"]}
        assert kinds.get("ChipType") == "enum_mismatch"

    def test_clean_table_has_zero_errors(self):
        # minimal fixture 无 template 注解 → 无约束 → 无异常
        g = build_graph(FIXTURES / "minimal.expected")
        for n in g["nodes"]:
            assert n["error_count"] == 0

    def test_hex_value_range_check(self):
        # RunMode=0x10000000 (~268M) vs ResAllocMode @range:0-3 不冲突；
        # 该字段数据是 0 → 不触发；验证 hex string 不会让 _to_numeric 崩
        g = build_graph(FIXTURES / "multi_runmode.expected")
        # 不应抛异常，且 RunModeTbl 的 ResAllocMode=0 在范围内
        n = _by_id(g["nodes"], "0x10000000/RunModeTbl")
        # ResAllocMode 在 table_attributes 不进 record，所以不在 record.errors
        # 这条 test 只验 hex 字符串解析路径不崩
        assert isinstance(n["error_count"], int)


# endregion

# region hex preservation — 嵌入式可读性命脉 ───────────────────────────────
class TestHexPreservation:
    """yaml ``0x10000000`` / ``0x0001`` / ``0xDEADBEEF`` 等 hex 字面在 JSON 输出
    必须保留 ``0x...`` 形态（保 width + 大小写），不能退化为十进制 int."""

    def test_hex_value_preserves_lowercase_prefix(self):
        g = build_graph(FIXTURES / "multi_runmode.expected")
        n = _by_id(g["nodes"], "0x10000000/RunModeTbl")
        # 顶层 RunMode: 0x10000000 应保留为字符串 "0x10000000"
        assert n["table_attributes"]["RunMode"] == "0x10000000"

    def test_hex_value_preserves_width_padding(self):
        g = build_graph(FIXTURES / "hex_widths.expected")
        n = _by_id(g["nodes"], "HexTbl")
        # 第二条 record 的 Width8 = 0x00000001（width=8 必须保留）
        widths = [r["attribute"] for r in n["records"]]
        assert "0x00000001" in [r.get("Width8") for r in widths]
        assert "0x0001" in [r.get("Width4") for r in widths]
        assert "0x01" in [r.get("Width2") for r in widths]

    def test_hex_value_preserves_uppercase_case(self):
        g = build_graph(FIXTURES / "hex_widths.expected")
        n = _by_id(g["nodes"], "HexTbl")
        widths = [r["attribute"] for r in n["records"]]
        # 0xAB / 0xABCD / 0xDEADBEEF / 0xCAFE 都是大写
        assert "0xAB" in [r.get("Width2") for r in widths]
        assert "0xABCD" in [r.get("Width4") for r in widths]
        assert "0xDEADBEEF" in [r.get("Width8") for r in widths]


# endregion

# region all fixtures smoke ─────────────────────────────────────────────────
@pytest.mark.parametrize("fixture", ["minimal", "empty_table", "hex_widths", "multi_runmode"])
def test_all_fixtures_build_smoke(fixture):
    g = build_graph(FIXTURES / f"{fixture}.expected")
    assert g["meta"]["node_count"] > 0
    assert isinstance(g["edges"], list)
    assert isinstance(g["referenced_by"], dict)
    json.dumps(g)  # JSON 可序列化


# endregion
