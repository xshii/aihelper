"""YAML Schema 合规性测试 — 验证所有 fixture 符合 docs/yaml-schema.md 规范。

静态合规（首行 / 命名 / 注解形式）+ 字节级 round-trip + 幂等性。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from ruamel.yaml import YAML, YAMLError

from ecfg.legacy.postprocess import pack
from ecfg.legacy.preprocess import unpack, unpack_many

_yaml = YAML(typ="safe")

FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "xml" / "valid"

ELEMENT_HEADER = re.compile(r"^#\s*@element:(<self>|[A-Za-z][A-Za-z0-9_]*)\s*$")
ANNOTATION_NEEDS_NO_SPACE = re.compile(r"@(element|related|use|range|merge|enum):\s")


def _norm_xml(text: str) -> str:
    """语义级 XML 比对：折叠所有连续空白为单空格。"""
    return re.sub(r"\s+", " ", text).strip()


def discover_fixtures() -> list[Path]:
    """所有 ``<name>.expected/`` 目录."""
    return sorted(FIXTURES_ROOT.glob("*.expected"))


def discover_yaml_files(fixture_dir: Path) -> list[Path]:
    """所有 element yaml 文件，跳过下划线前缀的 meta 文件（如 _children_order.yaml）。"""
    return sorted(p for p in fixture_dir.rglob("*.yaml") if not p.name.startswith("_"))


@pytest.fixture(params=discover_fixtures(), ids=lambda p: p.name)
def fixture_dir(request: pytest.FixtureRequest) -> Path:
    """parametrized fixture：每个 ``<name>.expected/`` 目录单独跑一遍合规."""
    return request.param


class TestFixtureLayout:
    """目录布局与命名（R1/R2/R3）."""

    def test_no_restbl_prefix(self, fixture_dir: Path) -> None:
        """R3：文件 stem 不带 ``ResTbl_`` 前缀."""
        offenders = [p for p in fixture_dir.rglob("*.yaml") if p.name.startswith("ResTbl_")]
        assert not offenders, f"找到 ResTbl_ 前缀文件（违反 R3）: {offenders}"

    def test_has_fileinfo(self, fixture_dir: Path) -> None:
        """每个 fixture 必有恰好一份 FileInfo.yaml（根目录或 shared/）."""
        candidates = [
            fixture_dir / "FileInfo.yaml",
            fixture_dir / "shared" / "FileInfo.yaml",
        ]
        existing = [p for p in candidates if p.is_file()]
        assert len(existing) == 1, f"FileInfo.yaml 必须恰好一份；实际：{existing}"

    def test_no_empty_shared(self, fixture_dir: Path) -> None:
        """R2：无 scope folder 的 fixture 不应使用 shared/."""
        scope_folders = [p for p in fixture_dir.iterdir() if p.is_dir() and p.name.startswith("0x")]
        shared = fixture_dir / "shared"
        if not scope_folders and shared.is_dir():
            pytest.fail(f"{fixture_dir.name} 无 scope folder，不应使用 shared/")


class TestFirstLine:
    """R4: 每个 element yaml 首行必须 # @element:<X>。

    例外：FileInfo.yaml 是文档根，元素名固定 ``FileInfo``，无需头。
    """

    def test_every_yaml_has_element_header(self, fixture_dir: Path) -> None:
        """除 FileInfo 外，每个 element yaml 首行必符 ELEMENT_HEADER."""
        for yaml_file in discover_yaml_files(fixture_dir):
            if yaml_file.name == "FileInfo.yaml":
                continue  # 文档根例外
            first_line = yaml_file.read_text(encoding="utf-8").splitlines()[0]
            assert ELEMENT_HEADER.match(first_line), (
                f"{yaml_file.relative_to(FIXTURES_ROOT)} 首行不符 R4 格式：{first_line!r}"
            )


class TestYamlValidity:
    """每个 yaml 文件（含 meta）必须能被解析（语法合法）."""

    def test_yaml_parses(self, fixture_dir: Path) -> None:
        """所有 yaml 文件 ruamel 能解析."""
        for yaml_file in sorted(fixture_dir.rglob("*.yaml")):
            try:
                _yaml.load(yaml_file.read_text(encoding="utf-8"))
            except YAMLError as e:
                pytest.fail(f"{yaml_file.relative_to(FIXTURES_ROOT)} YAML 解析失败：{e}")


class TestChildrenOrder:
    """每个 fixture 必须有 template/_children_order.yaml（meta 文件，定义 emit 顺序）."""

    def test_children_order_meta_file_exists(self, fixture_dir: Path) -> None:
        """meta 文件必存在."""
        meta = fixture_dir / "template" / "_children_order.yaml"
        assert meta.is_file(), f"{fixture_dir.name} 缺少 {meta.relative_to(fixture_dir)}"

    def test_children_order_is_list_of_strings(self, fixture_dir: Path) -> None:
        """meta 文件必须是 yaml list-of-strings."""
        meta = fixture_dir / "template" / "_children_order.yaml"
        if not meta.is_file():
            pytest.skip("_children_order.yaml 不存在（前一个 test 应已报错）")
        loaded = _yaml.load(meta.read_text(encoding="utf-8"))
        assert isinstance(loaded, list) and all(isinstance(x, str) for x in loaded), (
            f"{meta.relative_to(FIXTURES_ROOT)} 必须是 yaml list-of-strings，实际：{loaded!r}"
        )


class TestAnnotationConsistency:
    """注解形式：冒号后无空格（@related:T.c 而非 @related: T.c）."""

    def test_no_space_after_colon_in_annotations(self, fixture_dir: Path) -> None:
        """扫所有 element yaml 看是否有 ``@xxx: value``（冒号后空格）."""
        for yaml_file in discover_yaml_files(fixture_dir):
            for lineno, line in enumerate(yaml_file.read_text(encoding="utf-8").splitlines(), 1):
                if ANNOTATION_NEEDS_NO_SPACE.search(line):
                    pytest.fail(
                        f"{yaml_file.relative_to(FIXTURES_ROOT)}:{lineno} "
                        f"注解冒号后有空格：{line.rstrip()!r}"
                    )


class TestPackSortDeterminism:
    """``pack()`` 输出在同一 fixture 上必须**幂等**——多次调用 byte-for-byte 一致."""

    def test_repeated_pack_byte_identical(self, fixture_dir: Path) -> None:
        """跑 3 次 pack 必须产出完全相同的字节（无任何随机/字典序抖动）."""
        a, b, c = pack(fixture_dir), pack(fixture_dir), pack(fixture_dir)
        assert a == b == c


class TestChildrenOrderSpecificEntry:
    """``_children_order.yaml`` 的 ``<element>:<stem>`` 特例语法 — pin 单个 instance."""

    def test_specific_entry_overrides_default_sort(
        self, tmp_path: Path,
    ) -> None:
        """特例条 ``ResTbl:CapacityRunModeMapTbl`` 应让 wrapper 在默认字母序前 emit."""
        import shutil
        src = FIXTURES_ROOT / "multi_runmode.expected"
        dst = tmp_path / "fx.expected"
        shutil.copytree(src, dst)
        # 当前 _children_order.yaml 已含特例，pack 出 wrapper 在 flats 之前
        emitted = pack(dst)
        wrapper_pos = emitted.find('CapacityRunModeMapTbl="CapacityRunModeMapTbl"')
        flat_pos = emitted.find('<CapacityRunModeMapTbl CapacityID="0x0001"')
        assert wrapper_pos > 0 and flat_pos > 0
        assert wrapper_pos < flat_pos, (
            f"wrapper 应该在 flats 之前；wrapper@{wrapper_pos}, flat@{flat_pos}"
        )

    def test_without_specific_entry_falls_back_to_alphabetical(
        self, tmp_path: Path,
    ) -> None:
        """删掉特例条 → 默认字母序：flat element 名 ``Cap...`` < ``ResTbl``，flats 先于 wrapper."""
        import shutil
        src = FIXTURES_ROOT / "multi_runmode.expected"
        dst = tmp_path / "fx.expected"
        shutil.copytree(src, dst)
        # 把 _children_order.yaml 改成无特例的版本
        order_file = dst / "template" / "_children_order.yaml"
        order_file.write_text(
            "- RatVersion\n"
            "- CapacityRunModeMapTbl\n"
            "- RunModeTbl\n"
            "- ClkCfgTbl\n"
            "- DmaCfgTbl\n"
            "- CoreDeployTbl\n",
            encoding="utf-8",
        )
        emitted = pack(dst)
        wrapper_pos = emitted.find('CapacityRunModeMapTbl="CapacityRunModeMapTbl"')
        flat_pos = emitted.find('<CapacityRunModeMapTbl CapacityID="0x0001"')
        # 字母序：flat element 名 "CapacityRunModeMapTbl" 排在 wrapper element 名 "ResTbl" 前
        assert flat_pos < wrapper_pos, (
            f"无特例时按字母序，flats 应该先于 wrapper；wrapper@{wrapper_pos}, flat@{flat_pos}"
        )


class TestPackWarnings:
    """post-process WARNING 路径必须真实触发（防数据静默丢失）."""

    def test_orphan_yaml_warns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """fixture 里有但 ``_children_order`` 没列的 yaml → WARNING."""
        import shutil

        src = FIXTURES_ROOT / "minimal.expected"
        dst = tmp_path / "minimal.expected"
        shutil.copytree(src, dst)
        (dst / "OrphanTbl.yaml").write_text(
            "# @element:ResTbl\nLineNum: # @related:count(Line)\n",
            encoding="utf-8",
        )
        with caplog.at_level("WARNING", logger="ecfg.legacy.postprocess"):
            pack(dst)
        assert "OrphanTbl.yaml" in caplog.text
        assert "_children_order" in caplog.text

    def test_unused_class_entry_warns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """``_children_order`` 列了但 fixture 找不到匹配文件 → WARNING."""
        import shutil

        src = FIXTURES_ROOT / "minimal.expected"
        dst = tmp_path / "minimal.expected"
        shutil.copytree(src, dst)
        order_file = dst / "template" / "_children_order.yaml"
        order_file.write_text(
            order_file.read_text(encoding="utf-8") + "- NoSuchTbl\n",
            encoding="utf-8",
        )
        with caplog.at_level("WARNING", logger="ecfg.legacy.postprocess"):
            pack(dst)
        assert "NoSuchTbl" in caplog.text


class TestRoundTripBytes:
    """字节级 round-trip — 调 ``ecfg.legacy.postprocess.pack`` 把 yaml 树拼回 XML。

    与原 XML 做语义级比对（折叠所有连续空白为单空格）。
    """

    def test_pack_emits_byte_stable_xml(self, fixture_dir: Path) -> None:
        """``pack(fixture)`` 产物与配套 ``.xml`` 语义级一致."""
        xml_source = fixture_dir.with_suffix(".xml")
        assert xml_source.is_file(), f"缺少配套 XML：{xml_source}"

        emitted = pack(fixture_dir)
        original = xml_source.read_text(encoding="utf-8")
        assert _norm_xml(emitted) == _norm_xml(original), (
            f"\n--- emitted ---\n{emitted}\n--- original ---\n{original}"
        )


class TestUnpackFolderIdentity:
    """unpack 产物与 ``.expected/`` 目录字节级一致（仅 data 文件，``template/`` 豁免）。

    Why exclude template/：``template/_children_order.yaml`` 是人工带教学注释的产物，
    设计上允许 fixture 比 preprocess 多写解释；data yamls 必须严格 == preprocess 输出。
    """

    def test_unpack_byte_identical_to_fixture(
        self, fixture_dir: Path, tmp_path: Path,
    ) -> None:
        """所有非 template/ yaml 文件，unpack 输出 must 字节级 == fixture."""
        xml_source = fixture_dir.with_suffix(".xml")
        out = tmp_path / fixture_dir.name
        unpack(xml_source, out)

        mismatches: list[str] = []
        for fixture_file in fixture_dir.rglob("*.yaml"):
            if "template" in fixture_file.parts:
                continue
            rel = fixture_file.relative_to(fixture_dir)
            our_file = out / rel
            if not our_file.exists():
                mismatches.append(f"{rel} (missing in unpack)")
                continue
            if our_file.read_bytes() != fixture_file.read_bytes():
                mismatches.append(f"{rel} (content differs)")

        for our_file in out.rglob("*.yaml"):
            if "template" in our_file.parts:
                continue
            rel = our_file.relative_to(out)
            if not (fixture_dir / rel).exists():
                mismatches.append(f"{rel} (extra in unpack)")

        assert not mismatches, (
            f"{fixture_dir.name}：unpack 与 fixture data 文件不一致：{mismatches}"
        )


class TestFullRoundTrip:
    """完整 XML → unpack → pack → 字节级回到原 XML。

    验证 ``ecfg.legacy.preprocess.unpack`` 与 ``postprocess.pack`` 互为完整逆操作。
    """

    def test_xml_to_yaml_to_xml_byte_identical(
        self, fixture_dir: Path, tmp_path: Path,
    ) -> None:
        """从 ``.xml`` 出发：unpack → 中间 yaml 树 → pack 拼回，必须严格字节级一致."""
        xml_source = fixture_dir.with_suffix(".xml")
        assert xml_source.is_file(), f"缺少配套 XML：{xml_source}"
        original = xml_source.read_text(encoding="utf-8")

        intermediate = tmp_path / fixture_dir.name
        unpack(xml_source, intermediate)
        emitted = pack(intermediate)

        assert emitted == original, (
            f"XML→YAML→XML 必须字节级一致；fixture={fixture_dir.name}"
        )


_MERGE_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<FileInfo FileName="merge.xlsx" Date="2026/04" XmlConvToolsVersion="V0.01" '
    'RatType="" Version="1.00" RevisionHistory="">\n'
)
_MERGE_RATVERSION = (
    '    <ResTbl RatVersion="RatVersion" LineNum="1">\n'
    '        <Line VVersion="100" RVersion="22" CVersion="10"/>\n'
    '    </ResTbl>\n'
)
_MERGE_FOO = (
    '    <ResTbl FooTbl="FooTbl" LineNum="1">\n'
    '        <Line Id="0" Name="alpha"/>\n'
    '    </ResTbl>\n'
)
_MERGE_FOO_CONFLICT = (
    '    <ResTbl FooTbl="FooTbl" LineNum="1">\n'
    '        <Line Id="0" Name="OOPS"/>\n'
    '    </ResTbl>\n'
)
_MERGE_BAR = (
    '    <ResTbl BarTbl="BarTbl" LineNum="1">\n'
    '        <Line Id="1" Name="beta"/>\n'
    '    </ResTbl>\n'
)


class TestUnpackMany:
    """多 XML 合并：幂等去重 + 冲突检测 + 跨 XML 顺序保持."""

    def test_idempotent_dedup_then_pack_byte_identical(self, tmp_path: Path) -> None:
        """xml_a [RatVer, Foo] + xml_b [Foo (dup), Bar] → 合并去重 → [RatVer, Foo, Bar]."""
        a = tmp_path / "a.xml"
        b = tmp_path / "b.xml"
        a.write_text(
            _MERGE_HEADER + _MERGE_RATVERSION + _MERGE_FOO + "</FileInfo>", encoding="utf-8",
        )
        b.write_text(_MERGE_HEADER + _MERGE_FOO + _MERGE_BAR + "</FileInfo>", encoding="utf-8")
        merged_expected = (
            _MERGE_HEADER + _MERGE_RATVERSION + _MERGE_FOO + _MERGE_BAR + "</FileInfo>\n"
        )

        out = tmp_path / "merged"
        unpack_many([a, b], out)
        emitted = pack(out)
        assert emitted == merged_expected, (
            f"\n--- emitted ---\n{emitted}\n--- expected ---\n{merged_expected}"
        )

    def test_conflict_same_wrapper_key_different_content_raises(
        self, tmp_path: Path,
    ) -> None:
        """相同 wrapper key (ResTbl, FooTbl) 在两份 XML 中字段不同 → ValueError."""
        a = tmp_path / "a.xml"
        b = tmp_path / "b.xml"
        a.write_text(_MERGE_HEADER + _MERGE_FOO + "</FileInfo>", encoding="utf-8")
        b.write_text(_MERGE_HEADER + _MERGE_FOO_CONFLICT + "</FileInfo>", encoding="utf-8")

        with pytest.raises(ValueError, match="非幂等去重"):
            unpack_many([a, b], tmp_path / "out")

    def test_fileinfo_attrs_conflict_raises(self, tmp_path: Path) -> None:
        """两份 XML 的 ``<FileInfo>`` attribute 不一致 → ValueError."""
        a = tmp_path / "a.xml"
        b = tmp_path / "b.xml"
        a.write_text(_MERGE_HEADER + "</FileInfo>", encoding="utf-8")
        b.write_text(
            _MERGE_HEADER.replace('FileName="merge.xlsx"', 'FileName="other.xlsx"')
            + "</FileInfo>",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="FileInfo 属性"):
            unpack_many([a, b], tmp_path / "out")

    def test_empty_xml_paths_raises(self, tmp_path: Path) -> None:
        """空列表 → ValueError，不静默."""
        with pytest.raises(ValueError, match="不能为空"):
            unpack_many([], tmp_path / "out")


class TestCountAttrAmbiguity:
    """G3：值匹配 ``len(children)`` 的 attribute 多个时 → WARNING + 选首个；唯一时静默."""

    def test_ambiguous_count_attr_warns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """构造一个有两个 int=3 的 attribute → 触发 WARNING."""
        xml = tmp_path / "ambig.xml"
        xml.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<FileInfo FileName="x" Date="" XmlConvToolsVersion="" RatType="" '
            'Version="" RevisionHistory="">\n'
            '    <AmbigTbl ResAllocMode="3" ResTblNum="3">\n'
            '        <RunModeItem A="A"/>\n'
            '        <RunModeItem B="B"/>\n'
            '        <RunModeItem C="C"/>\n'
            '    </AmbigTbl>\n'
            '</FileInfo>\n',
            encoding="utf-8",
        )
        with caplog.at_level("WARNING", logger="ecfg.legacy.preprocess"):
            unpack(xml, tmp_path / "out")
        assert "count 锚字段歧义" in caplog.text

    def test_unique_count_attr_does_not_warn(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """唯一匹配 → 不应触发歧义 WARNING（防止误报）."""
        xml = tmp_path / "unique.xml"
        xml.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<FileInfo FileName="x" Date="" XmlConvToolsVersion="" RatType="" '
            'Version="" RevisionHistory="">\n'
            '    <UniqueTbl ResAllocMode="0" ResTblNum="2">\n'
            '        <RunModeItem A="A"/>\n'
            '        <RunModeItem B="B"/>\n'
            '    </UniqueTbl>\n'
            '</FileInfo>\n',
            encoding="utf-8",
        )
        with caplog.at_level("WARNING", logger="ecfg.legacy.preprocess"):
            unpack(xml, tmp_path / "out")
        assert "count 锚字段歧义" not in caplog.text


class TestUseAnnotation:
    """G1：跨目录 ref 自动加 ``# @use:<rel-path>`` 行尾注释."""

    def test_cross_folder_ref_emits_use_annotation(self, tmp_path: Path) -> None:
        """``0x10000000/RunModeTbl.yaml`` 引用 ``shared/DmaCfgTbl`` → 必有 @use 注释."""
        src = FIXTURES_ROOT / "multi_runmode.xml"
        out = tmp_path / "mr"
        unpack(src, out)
        yaml_text = (out / "0x10000000" / "RunModeTbl.yaml").read_text(encoding="utf-8")
        assert "@use:../shared/DmaCfgTbl.yaml" in yaml_text, (
            f"跨目录 ref 应该加 @use；实际内容：\n{yaml_text}"
        )

    def test_same_folder_ref_does_not_emit_use(self, tmp_path: Path) -> None:
        """``0x10000000/RunModeTbl.yaml`` 引用同 folder 的 ``ClkCfgTbl`` → 不应有 @use."""
        src = FIXTURES_ROOT / "multi_runmode.xml"
        out = tmp_path / "mr"
        unpack(src, out)
        yaml_text = (out / "0x10000000" / "RunModeTbl.yaml").read_text(encoding="utf-8")
        # ClkCfgTbl 在 0x10000000 同 folder（本 fixture 中）
        clk_lines = [line for line in yaml_text.splitlines() if "ClkCfgTbl" in line]
        assert clk_lines and not any("@use" in line for line in clk_lines), (
            f"同 folder ref 不应加 @use；ClkCfgTbl 行：{clk_lines}"
        )

    def test_ambiguous_stem_across_folders_warns_and_skips(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """同 stem 存在于多 folder + ref 来自第三处 → WARNING + 不输出 @use（不猜路径）."""
        # 两个 RunModeTbl 制造 stem='RunModeTbl' 的多 folder 状态
        # ExtraTbl 落在 shared/，其子 ExtraItem 引用 'RunModeTbl' → 触发歧义
        xml = tmp_path / "ambig.xml"
        xml.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<FileInfo FileName="x" Date="" XmlConvToolsVersion="" RatType="" '
            'Version="" RevisionHistory="">\n'
            '    <RunModeTbl RunMode="0x1" ResAllocMode="0" ResTblNum="0"/>\n'
            '    <RunModeTbl RunMode="0x2" ResAllocMode="0" ResTblNum="0"/>\n'
            '    <ExtraTbl ExtraNum="1">\n'
            '        <ExtraItem Tgt="RunModeTbl"/>\n'
            '    </ExtraTbl>\n'
            '</FileInfo>\n',
            encoding="utf-8",
        )
        out = tmp_path / "out"
        with caplog.at_level("WARNING", logger="ecfg.legacy.preprocess"):
            unpack(xml, out)
        assert "跨多个 folder" in caplog.text
        extra_text = (out / "shared" / "ExtraTbl.yaml").read_text(encoding="utf-8")
        assert "@use" not in extra_text, (
            f"歧义情况下不应猜路径；实际：\n{extra_text}"
        )


_RUNMODE_A = (
    '    <RunModeTbl RunMode="0x1" ResAllocMode="0" ResTblNum="1">\n'
    '        <RunModeItem Foo="Foo"/>\n'
    '    </RunModeTbl>\n'
)
_RUNMODE_A_CONFLICT = (
    '    <RunModeTbl RunMode="0x1" ResAllocMode="9" ResTblNum="1">\n'
    '        <RunModeItem Foo="Foo"/>\n'
    '    </RunModeTbl>\n'
)


class TestUnpackManyExtra:
    """补强测试：自命名（带 RunMode）冲突 + 非 FileInfo 根."""

    def test_self_named_runmode_conflict_raises(self, tmp_path: Path) -> None:
        """同 ``(RunModeTbl, RunMode=0x1)`` 在两份 XML 中字段不同 → ValueError."""
        a = tmp_path / "a.xml"
        b = tmp_path / "b.xml"
        a.write_text(_MERGE_HEADER + _RUNMODE_A + "</FileInfo>", encoding="utf-8")
        b.write_text(_MERGE_HEADER + _RUNMODE_A_CONFLICT + "</FileInfo>", encoding="utf-8")
        with pytest.raises(ValueError, match="非幂等去重"):
            unpack_many([a, b], tmp_path / "out")

    def test_non_fileinfo_root_raises(self, tmp_path: Path) -> None:
        """根元素不是 ``<FileInfo>`` → ValueError，不静默接受."""
        bad = tmp_path / "bad.xml"
        bad.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<NotFileInfo/>\n',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="root must be <FileInfo>"):
            unpack(bad, tmp_path / "out")
