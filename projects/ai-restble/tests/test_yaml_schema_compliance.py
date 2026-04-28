"""YAML Schema 合规性测试 — 验证所有 fixture 符合 docs/yaml-schema.md 规范。

不依赖 skill 实现；只检查 fixture 静态合规。round-trip 字节级测试在 skill 实现后启用
（标记 xfail 占位；strict=True 强制：skill 上线后必须移除 xfail）。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Pattern

import pytest
from ruamel.yaml import YAML, YAMLError

from ecfg.legacy.postprocess import pack

_yaml = YAML(typ="safe")

FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "xml" / "valid"

# 已废弃形态（fixture 内出现就违规）。`@enum` `@range` `@merge` 是规范保留注解，不在此列。
OBSOLETE_PATTERNS: list[tuple[Pattern[str], str]] = [
    (re.compile(r"@derived:"), "用 @related: 替代"),
    (re.compile(r"@ref\b"), "用 @related（无括号 = identity）"),
    (re.compile(r"@noconflict_group\b"), "已删除；merge-safety 由 per-field @merge 有/无推断"),
    (re.compile(r"^#\s*@toplevel\b", re.MULTILINE), "用 # @element:<self> 替代"),
    (re.compile(r"^attribute:\s*$", re.MULTILINE), "顶层 attribute: 包裹已废弃；扁平 mapping"),
]

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


class TestObsoleteForms:
    """fixture 不应出现旧形态/已删注解（含 meta 文件）."""

    def test_no_obsolete_annotations(self, fixture_dir: Path) -> None:
        """扫所有 yaml（含 meta）确认无 OBSOLETE_PATTERNS."""
        all_yaml = sorted(fixture_dir.rglob("*.yaml"))
        for yaml_file in all_yaml:
            content = yaml_file.read_text(encoding="utf-8")
            for pattern, hint in OBSOLETE_PATTERNS:
                if pattern.search(content):
                    pytest.fail(
                        f"{yaml_file.relative_to(FIXTURES_ROOT)} 含过时形态 "
                        f"`{pattern.pattern}` ({hint})"
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
