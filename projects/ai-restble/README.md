# ai-restble — ecfg

YAML-first 嵌入式资源配置表工具。取代 Excel，支持 legacy XML 字节级 round-trip、
关联关系显式化、机器校验、版本可控、AI 友好。

## 核心能力

| 能力 | CLI 命令 | Python API | 状态 |
|------|---------|-----------|------|
| **Legacy XML → YAML 文件树** | `ecfg unpack`（多 XML 幂等去重合一） | `ecfg.legacy.preprocess.unpack` / `unpack_many` | ✅ |
| **YAML 文件树 → Legacy XML**（字节级稳定） | `ecfg pack` | `ecfg.legacy.postprocess.pack` | ✅ |
| **从 XML 生成 schema scaffold** | `ecfg scaffold` | `ecfg.legacy.scaffold.generate_scaffolds` | ✅ |
| Excel ↔ YAML 互转 | `ecfg import-excel` / `export-excel` | `ecfg.io.importers.excel` / `exporters.excel` | ✅ |
| XML ↔ YAML 互转（通用 schema 形态，非 legacy） | `ecfg import-xml` / `export-xml` | `ecfg.io` | ✅ |
| 多 team YAML merge engine（schema-aware） | — | `ecfg.merge.merger.merge_tables` | ✅ |
| Schema validator（@range/@enum/@merge） | — | `ecfg.schema.validator.validate_table` | ✅ |
| 占位画布（前端 read-only） | `ecfg serve` | — | 🚧 Phase 0 占位页 |
| `ecfg validate` / `expand` | `ecfg validate` | — | 📋 Phase 1 stub |

## 安装

```bash
pip install -e '.[dev]'
```

## Quickstart：Legacy XML round-trip + schema scaffold

主力使用场景：把 legacy XML 拆成 YAML 文件树编辑/版本管理/合并，再合回字节级一致的 XML。

### 1. XML → YAML 文件树

```bash
ecfg unpack tests/fixtures/xml/valid/multi_runmode.xml /tmp/tree
# unpack: 1 XML(s) → /tmp/tree/
```

产出：

```
/tmp/tree/
├── shared/                          ← 跨 RunMode 共享数据
│   ├── FileInfo.yaml
│   ├── DmaCfgTbl.yaml
│   └── ...
├── 0x10000000/                      ← scope-bound 数据（per RunMode）
│   ├── RunModeTbl.yaml
│   ├── ClkCfgTbl.yaml
│   └── ...
├── 0x20000000/
│   └── ...
└── template/
    └── _children_order.yaml         ← 顶层 emit 顺序 meta
```

每个 data yaml 自描述（首行 `# @element:<X>`），跨目录 ref 自动加 `# @use:<rel>` 提示。

### 2. YAML 文件树 → XML（round-trip 验证）

```bash
ecfg pack /tmp/tree -o /tmp/out.xml
diff tests/fixtures/xml/valid/multi_runmode.xml /tmp/out.xml
# 字节级一致（无差异输出）
```

### 3. 多 XML 合一

```bash
ecfg unpack baseline.xml patch1.xml patch2.xml /tmp/merged
# 同 (element, type-attr) 跨 XML 必须字段完全相同；冲突即 raise
```

### 4. 生成 schema scaffold（约束/范围/FK 占位）

```bash
ecfg scaffold tests/fixtures/xml/valid/multi_runmode.xml -o /tmp/tree
# scaffold: 1 XML(s) → /tmp/tree/template/
```

新增的 scaffold（`/tmp/tree/template/shared/DmaCfgTbl.yaml` 等）：

```yaml
# @element:ResTbl
LineNum: # @related:count(Line)
- ChannelId:        # ← 你后填 @range:0-15 等约束
  SrcType:          # ← 你后填 @enum:MEM,DEV,...
  DstType:
  BurstSize:
```

scaffold 文件**只描述结构骨架**，约束/合并规则/FK 由你后填。再次跑 `ecfg scaffold` 会
overwrite（除非你先备份编辑过的版本）。

### 5. 字节级一致性保证

```python
from pathlib import Path
import tempfile
from ecfg.legacy.preprocess import unpack
from ecfg.legacy.postprocess import pack

src = Path("tests/fixtures/xml/valid/multi_runmode.xml")
with tempfile.TemporaryDirectory() as td:
    unpack(src, Path(td))
    emitted = pack(Path(td))
assert emitted == src.read_text(encoding="utf-8")  # ✓ 字节级一致
```

## 项目结构

```
src/ecfg/
├── model.py                    # Record / Table / CellValue（layer 0，generic）
├── cli.py                      # click CLI 入口
├── app.py                      # Flask create_app（占位）
├── legacy/                     # Legacy XML round-trip + scaffold（独立 track）
│   ├── const.py                # 协议常量集中（XML tag/attr/folder/annotation）
│   ├── preprocess.py           # XML → YAML 拆解（unpack / unpack_many）
│   ├── postprocess.py          # YAML → XML 字节级稳定合成（pack）
│   └── scaffold.py             # 从 XML 生成 template/<E>.yaml schema scaffold
├── schema/                     # Schema 模型 + TEMPLATE 块解析 + validator
│   ├── const.py
│   ├── model.py                # FieldSchema / TableSchema / Region literal
│   ├── annotations.py          # @key:value mini-parser
│   ├── loader.py               # TEMPLATE BEGIN/END → TableSchema
│   └── validator.py            # @range/@enum/合并约束运行期校验
├── merge/                      # 多 team yaml merge engine
│   ├── const.py                # 6 个 merge op
│   ├── policies.py             # concat/sum/max/min/union/conflict
│   └── merger.py
└── io/                         # Excel/XML/YAML importer + exporter
    ├── importers/              # excel.py / xml.py / yaml.py
    └── exporters/              # excel.py / xml.py / yaml.py

docs/
├── yaml-schema.md              # Legacy XML round-trip 协议（必读）
├── merge-spec.md               # Multi-team merge engine 规范
└── design-completeness.md      # 完备性 + 可扩展性 + TODO（编译语言视角）

prompts/                        # Skill 实现 prompt（喂给弱 AI）
├── skill-preprocess.md         # XML → YAML 拆解 skill
├── skill-postprocess.md        # YAML → XML 合成 skill
└── skill-scaffold.md           # XML → template scaffold skill

tests/
├── fixtures/xml/valid/         # 4 fixture：minimal/empty_table/hex_widths/multi_runmode
├── test_yaml_schema_compliance.py   # 主力测试（fixture round-trip + scaffold + merge）
├── test_cli.py                 # CLI 入口
├── test_excel_importer.py / test_io_roundtrip.py
├── test_schema_loader.py / test_validator.py / test_annotations.py / test_comments.py
├── test_merger.py
├── test_graph_builder.py       # Phase 2A graph builder
├── test_api_graph.py           # Flask /api/graph 端点
└── test_browser_smoke.py       # Phase 2A 前端 Playwright 交互冒烟
```

## 运行测试

```bash
# 主测试套件（不依赖浏览器，~250 项秒级跑完）
pytest -q

# 含前端交互冒烟（需先装 Playwright 一次）
pip install playwright pytest-playwright
playwright install chromium    # ~80MB 一次性下载
pytest -q                       # test_browser_smoke 自动接入
```

## 浏览器手动验真

```bash
ecfg serve --port 5050
# 浏览器打开 http://127.0.0.1:5050/?path=tests/fixtures/xml/valid/multi_runmode.expected
```

测试覆盖：
- XML → unpack → pack → XML 字节级一致（4/4 fixtures）
- 多 XML 幂等去重 + 冲突检测（wrapper/RunMode 自命名/FileInfo attr）
- @use 跨目录 ref 自动注入 + 歧义警告
- count 锚字段歧义警告
- folder identity（unpack 输出 vs fixture，template/_children_order 豁免人工注释）
- scaffold 幂等性 + round-trip 一致性 + 字段集 union
- TEMPLATE 块解析、6 种 merge op、validator 约束、CLI

## 相关文档

- **`docs/yaml-schema.md`** — Legacy XML ↔ YAML round-trip 权威协议
- **`docs/merge-spec.md`** — Multi-team yaml merge 规范
- **`docs/design-completeness.md`** — 设计完备性论证（编译语言视角）+ TODO 路线图
- **`prompts/skill-{preprocess,postprocess,scaffold}.md`** — 弱 AI 实现/扩展时的 skill prompt
- **`PROMPT.md`** — 项目的 prompt 链索引
