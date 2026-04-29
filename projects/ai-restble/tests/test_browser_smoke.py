"""Phase 2A 前端交互冒烟 — Playwright + 真 Chromium，按行为表面积覆盖.

依赖：``pip install playwright pytest-playwright`` + ``playwright install chromium``。
未装 playwright 时 skip，不阻塞主测试套件。

覆盖维度（每维度独立 class）：

- 路径加载：URL 参数 / 输入+Enter / 输入+按钮 三入口
- 树结构：categories 投影完整、归类正确
- 树点击 + active 互斥
- 详情面板：节点 header / records / 三 region CSS / 首条自动展开
- 特殊形态：空 wrapper / FileInfo
- 节点切换：状态净化
- 错误 UX：banner 显示 + 可恢复
- JS 错误不变量：贯穿流程零 console error
"""
from __future__ import annotations

import re
import socket
import threading
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Page, expect  # noqa: E402

from ecfg.app import create_app  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "xml" / "valid"


# region live_server fixture ────────────────────────────────────────────────
def _free_port() -> int:
    """OS 分配空闲端口，避免与 dev 服务冲突."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server():
    """Werkzeug make_server 起 Flask 在后台线程，session 结束 shutdown."""
    port = _free_port()
    app = create_app()
    server = make_server("127.0.0.1", port, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


# endregion

# region helpers ────────────────────────────────────────────────────────────
def _fixture_dir(name: str) -> str:
    return str(FIXTURES / f"{name}.expected")


def _open_fixture(page: Page, base_url: str, fixture_name: str) -> None:
    """跳到 ``base_url/?path=<fixture>`` 并等树渲染完成（auto-wait）."""
    page.goto(f"{base_url}/?path={_fixture_dir(fixture_name)}")
    expect(page.locator(".tree-item").first).to_be_visible(timeout=5000)


def _click_tree(page: Page, node_id: str) -> None:
    """通过 data-node 属性点树项（最稳定的 selector）."""
    page.click(f'.tree-item[data-node="{node_id}"]')


# endregion

# region path loading — 三入口殊途同归 ──────────────────────────────────────
class TestPathLoading:
    def test_url_query_auto_loads_and_populates_input(
        self, page: Page, live_server: str,
    ):
        _open_fixture(page, live_server, "multi_runmode")
        expect(page.locator(".tree-item")).to_have_count(12)
        # path 输入框应回显被加载的路径
        assert "multi_runmode.expected" in page.input_value("#path-input")

    def test_load_button_triggers_load(self, page: Page, live_server: str):
        page.goto(live_server)
        page.fill("#path-input", _fixture_dir("empty_table"))
        page.click("#path-load")
        # empty_table fixture 有 4 个 yaml（BarTbl / FileInfo / FooTbl / RatVersion）
        expect(page.locator(".tree-item")).to_have_count(4, timeout=5000)

    def test_enter_key_triggers_load(self, page: Page, live_server: str):
        page.goto(live_server)
        page.fill("#path-input", _fixture_dir("minimal"))
        page.press("#path-input", "Enter")
        expect(page.locator(".tree-item")).to_have_count(3, timeout=5000)

    def test_load_updates_url_state(self, page: Page, live_server: str):
        page.goto(live_server)
        page.fill("#path-input", _fixture_dir("minimal"))
        page.click("#path-load")
        expect(page.locator(".tree-item").first).to_be_visible(timeout=5000)
        # history.replaceState 让 URL 含 ?path=...
        assert "minimal.expected" in page.url


# endregion

# region tree structure — graph JSON 镜像投影 ───────────────────────────────
class TestTreeStructure:
    def test_tree_shows_all_categories(self, page: Page, live_server: str):
        _open_fixture(page, live_server, "multi_runmode")
        cats = page.locator(".tree-cat")
        expect(cats).to_have_count(3)
        cat_texts = {el.inner_text() for el in cats.all()}
        assert cat_texts == {"shared", "0x10000000", "0x20000000"}

    def test_tree_node_count_matches_graph_node_count(
        self, page: Page, live_server: str,
    ):
        # multi_runmode = 12; minimal = 3; empty_table = 4
        _open_fixture(page, live_server, "minimal")
        expect(page.locator(".tree-item")).to_have_count(3)

    def test_scoped_node_ids_use_scope_prefix(self, page: Page, live_server: str):
        _open_fixture(page, live_server, "multi_runmode")
        # shared/ 前缀的 node 必出现在 multi_runmode 的树中
        expect(page.locator('.tree-item[data-node="shared/DmaCfgTbl"]')).to_be_visible()
        expect(
            page.locator('.tree-item[data-node="0x10000000/RunModeTbl"]')
        ).to_be_visible()


# endregion

# region tree click + active 互斥 ────────────────────────────────────────────
class TestTreeClickActive:
    def test_active_class_only_on_clicked_node(
        self, page: Page, live_server: str,
    ):
        _open_fixture(page, live_server, "multi_runmode")
        _click_tree(page, "shared/DmaCfgTbl")
        # 全局只有 1 个 .tree-item.active
        expect(page.locator(".tree-item.active")).to_have_count(1)
        expect(
            page.locator('.tree-item.active[data-node="shared/DmaCfgTbl"]')
        ).to_be_visible()

    def test_clicking_another_deactivates_previous(
        self, page: Page, live_server: str,
    ):
        _open_fixture(page, live_server, "multi_runmode")
        _click_tree(page, "shared/DmaCfgTbl")
        _click_tree(page, "0x10000000/RunModeTbl")
        # 仍然全局 1 个 active；目标节点是新的
        expect(page.locator(".tree-item.active")).to_have_count(1)
        expect(
            page.locator('.tree-item.active[data-node="0x10000000/RunModeTbl"]')
        ).to_be_visible()


# endregion

# region detail panel — 节点详情完整投影 ────────────────────────────────────
class TestNodeDetailPanel:
    def test_header_contains_id_scope_element_and_counts(
        self, page: Page, live_server: str,
    ):
        _open_fixture(page, live_server, "multi_runmode")
        _click_tree(page, "shared/DmaCfgTbl")
        header = page.locator("#panel .node-header")
        expect(header.locator("h5")).to_contain_text("shared/DmaCfgTbl")
        expect(header.locator("h5")).to_contain_text("shared")    # scope badge
        expect(header.locator("h5")).to_contain_text("ResTbl")    # element badge
        expect(header.locator("small")).to_contain_text("records")
        expect(header.locator("small")).to_contain_text("引用")

    def test_first_record_auto_open_others_collapsed(
        self, page: Page, live_server: str,
    ):
        # hex_widths/HexTbl 有 3 条 record 且无 template 注解 → 无 errors
        # 只有首条自动展开（错误 record 会 override 此规则强制展开，故选 clean fixture）
        _open_fixture(page, live_server, "hex_widths")
        _click_tree(page, "HexTbl")
        details = page.locator("#panel details")
        expect(details).to_have_count(3)
        assert details.first.evaluate("el => el.open") is True
        assert details.nth(1).evaluate("el => el.open") is False

    def test_field_region_css_classes_present(
        self, page: Page, live_server: str,
    ):
        _open_fixture(page, live_server, "multi_runmode")
        _click_tree(page, "shared/DmaCfgTbl")
        # legacy 数据全在 attribute 区
        expect(
            page.locator("#panel .field-group.region-attribute").first
        ).to_be_visible()

    def test_template_constraints_render_as_badges(
        self, page: Page, live_server: str,
    ):
        """有注解的 template → 字段标签旁出 @merge / range / enum 徽章."""
        _open_fixture(page, live_server, "multi_runmode")
        _click_tree(page, "shared/DmaCfgTbl")
        # SrcType 应显示 @enum 徽章
        enum_badge = page.locator("#panel .constr.enum").first
        expect(enum_badge).to_be_visible()
        # BurstSize 应显示 range 徽章 "1..8"（已 tighten 让 demo data 触发异常）
        range_badge = page.locator("#panel .constr.range").first
        expect(range_badge).to_be_visible()
        expect(range_badge).to_contain_text("8")
        # ChannelId 应显示 @merge:conflict 徽章
        merge_badge = page.locator("#panel .constr.merge").first
        expect(merge_badge).to_be_visible()
        expect(merge_badge).to_contain_text("conflict")


# endregion

# region 特殊形态 — 边界 fixture 不白屏 ──────────────────────────────────────
class TestEdgeShapes:
    def test_empty_wrapper_shows_no_record_message(
        self, page: Page, live_server: str,
    ):
        _open_fixture(page, live_server, "empty_table")
        # FooTbl in empty_table 是空 wrapper（LineNum count anchor only, 0 records）
        _click_tree(page, "FooTbl")
        expect(page.locator("#panel")).to_contain_text("该表暂无 record")

    def test_fileinfo_node_renders_with_fields(
        self, page: Page, live_server: str,
    ):
        _open_fixture(page, live_server, "minimal")
        _click_tree(page, "FileInfo")
        # FileInfo 在当前模型按 flat single record 处理 → 仍有 record summary
        expect(page.locator("#panel .node-header h5")).to_contain_text("FileInfo")
        expect(page.locator("#panel details").first).to_be_visible()


# endregion

# region 节点切换 — 状态净化 ────────────────────────────────────────────────
class TestSwitchingNodes:
    def test_switching_replaces_panel_completely(
        self, page: Page, live_server: str,
    ):
        _open_fixture(page, live_server, "multi_runmode")
        _click_tree(page, "shared/DmaCfgTbl")
        expect(page.locator("#panel .node-header h5")).to_contain_text("DmaCfgTbl")
        _click_tree(page, "shared/RatVersion")
        # 新节点 header 出现
        expect(page.locator("#panel .node-header h5")).to_contain_text("RatVersion")
        # 旧节点 header 消失（含 DmaCfgTbl 的元素都不存在）
        expect(page.locator("#panel")).not_to_contain_text("DmaCfgTbl")


# endregion

# region validation 异常显示 + 刷新 ─────────────────────────────────────────
class TestValidationDisplay:
    """template 约束 vs record 实际值的异常应在树/画布/面板三处可见."""

    def test_abnormal_table_marked_in_tree(self, page: Page, live_server: str):
        _open_fixture(page, live_server, "multi_runmode")
        # DmaCfgTbl 有 1 处 BurstSize 越界 → 树项加 .has-errors + 红 badge
        item = page.locator('.tree-item.has-errors[data-node="shared/DmaCfgTbl"]')
        expect(item).to_be_visible()
        expect(item.locator(".err-count")).to_contain_text("1")

    def test_clean_table_no_error_class(self, page: Page, live_server: str):
        _open_fixture(page, live_server, "multi_runmode")
        # FileInfo 无约束 → 不应有 .has-errors
        item = page.locator('.tree-item[data-node="shared/FileInfo"]')
        expect(item).to_be_visible()
        expect(item).not_to_have_class(re.compile(r".*has-errors.*"))

    def test_invalid_field_renders_red_with_message(
        self, page: Page, live_server: str,
    ):
        _open_fixture(page, live_server, "multi_runmode")
        _click_tree(page, "shared/DmaCfgTbl")
        # BurstSize 行应有 .invalid + .err-msg
        invalid = page.locator("#panel .field-row.invalid").first
        expect(invalid).to_be_visible()
        expect(invalid.locator(".err-msg")).to_contain_text("16")

    def test_node_header_shows_error_badge(
        self, page: Page, live_server: str,
    ):
        _open_fixture(page, live_server, "multi_runmode")
        _click_tree(page, "shared/CapacityRunModeMapTbl")
        # 顶部 header 有 .err-badge
        expect(page.locator("#panel .node-header .err-badge")).to_be_visible()


class TestRefreshButton:
    def test_refresh_button_reloads_current_path(
        self, page: Page, live_server: str,
    ):
        _open_fixture(page, live_server, "minimal")
        expect(page.locator(".tree-item")).to_have_count(3)
        page.click("#path-refresh")
        # 等待新一轮渲染（内容应仍然 3 个 item）
        expect(page.locator(".tree-item")).to_have_count(3)


# endregion

# region 视觉产物 — 截图固化到 tests/_artifacts/ 供人工 review ───────────────
ARTIFACTS = Path(__file__).parent / "_artifacts"


class TestVisualArtifacts:
    """跑一遍异常显示的关键视图，把截图写到 tests/_artifacts/（gitignored）.

    用途：人工 review 异常徽章 / 红框 / 错误消息的实际渲染效果，避免 assert
    通过但视觉上其实坏掉了。失败则测试报错；成功则留下截图供肉眼检查。
    """

    def test_capture_abnormal_display_flow(
        self, page: Page, live_server: str,
    ):
        ARTIFACTS.mkdir(exist_ok=True)
        page.set_viewport_size({"width": 1600, "height": 1000})
        _open_fixture(page, live_server, "multi_runmode")
        page.wait_for_timeout(800)  # echarts settle

        # overview：树 ⚠ 徽章 + canvas 红框节点
        page.screenshot(path=str(ARTIFACTS / "01_overview.png"))

        # 异常表（多重违反：enum + range×2）
        _click_tree(page, "shared/CapacityRunModeMapTbl")
        page.wait_for_timeout(300)
        page.screenshot(path=str(ARTIFACTS / "02_abnormal_multi_violations.png"))

        # 异常表（仅 range 违反）
        _click_tree(page, "shared/DmaCfgTbl")
        page.wait_for_timeout(300)
        page.screenshot(path=str(ARTIFACTS / "03_abnormal_range_only.png"))

        # 干净表对照
        _click_tree(page, "shared/RatVersion")
        page.wait_for_timeout(300)
        page.screenshot(path=str(ARTIFACTS / "04_clean_table.png"))

        # 留个最小断言：四张图都落盘了
        for name in (
            "01_overview.png",
            "02_abnormal_multi_violations.png",
            "03_abnormal_range_only.png",
            "04_clean_table.png",
        ):
            assert (ARTIFACTS / name).stat().st_size > 0


# endregion

# region 错误 UX — banner 显示 + 可恢复 ─────────────────────────────────────
class TestErrorBanner:
    def test_invalid_path_shows_red_banner_with_message(
        self, page: Page, live_server: str,
    ):
        page.goto(f"{live_server}/?path=/no/such/dir")
        banner = page.locator("#canvas-err.show")
        expect(banner).to_be_visible(timeout=3000)
        expect(banner).to_contain_text("yaml dir not found")
        expect(banner).to_contain_text("/no/such/dir")

    def test_loading_valid_path_clears_banner(
        self, page: Page, live_server: str,
    ):
        page.goto(f"{live_server}/?path=/no/such/dir")
        expect(page.locator("#canvas-err.show")).to_be_visible(timeout=3000)
        page.fill("#path-input", _fixture_dir("minimal"))
        page.click("#path-load")
        expect(page.locator(".tree-item").first).to_be_visible(timeout=5000)
        # banner 应失去 .show class
        expect(page.locator("#canvas-err")).to_have_class(
            re.compile(r"^err-banner$")
        )


# endregion

# region JS 错误不变量 — 贯穿流程零 console error ───────────────────────────
class TestNoConsoleErrors:
    def test_full_user_flow_emits_no_js_errors(
        self, page: Page, live_server: str,
    ):
        """模拟真实用户：load → click → switch → 触错 → 恢复 → click.

        过滤浏览器对 4xx 自动 emit 的 ``Failed to load resource``——本测试故意触发
        400，那条 log 是浏览器原生行为不是 JS bug。真正关心的是 ``pageerror``
        （uncaught exception）和我们 JS 代码主动 emit 的 ``console.error``。
        """
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))

        def _on_console(msg):
            if msg.type != "error":
                return
            if "Failed to load resource" in msg.text:
                return  # 浏览器对 4xx/5xx 的自动 log，非 JS bug
            errors.append(f"console.{msg.type}: {msg.text}")

        page.on("console", _on_console)

        _open_fixture(page, live_server, "multi_runmode")
        _click_tree(page, "shared/DmaCfgTbl")
        _click_tree(page, "0x10000000/RunModeTbl")

        # 触错
        page.fill("#path-input", "/no/such/dir")
        page.click("#path-load")
        expect(page.locator("#canvas-err.show")).to_be_visible(timeout=3000)

        # 恢复
        page.fill("#path-input", _fixture_dir("minimal"))
        page.click("#path-load")
        expect(page.locator(".tree-item").first).to_be_visible(timeout=5000)
        _click_tree(page, "FooTbl")

        # 留 200ms 让所有事件处理完
        page.wait_for_timeout(200)
        assert errors == [], "page emitted JS errors:\n  " + "\n  ".join(errors)


# endregion
