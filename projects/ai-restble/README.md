# ai-restble — ecfg

YAML-first 嵌入式资源配置表工具。取代 Excel，支持关联关系显式化、机器校验、版本可控、AI 友好。

## Phase 0（当前状态）

骨架已就位，可试用以下能力：

- `ecfg --help`                     — 查看命令列表
- `ecfg import-excel foo.xlsx`      — Excel → YAML tables（每 sheet 一文件）
- `ecfg import-xml merged.xml`      — XML → YAML tables
- `ecfg export-xml tables/`         — YAML → 单份 XML（硬件下游格式）
- `ecfg export-excel tables/`       — YAML → 单份 Excel
- `ecfg serve`                      — 启动 Flask 占位画布
- `ecfg validate / expand`          — 占位，Phase 1 实现

Phase 1+（loader / indexer / ref_resolver / aggregator / validator / graph_builder / yaml_writer）正在规划。

## 安装

```bash
pip install -e '.[dev]'
```

## 快速试用

### 1. Excel → YAML

```bash
# 默认每个 sheet 用第一列作 index，其余作 attribute
ecfg import-excel path/to/legacy.xlsx

# 指定复合 index（多对多关联表常用）
ecfg import-excel legacy.xlsx \
    --index-col "PinMux:bank,number,moduleType,moduleIndex" \
    --output-dir tables/
```

输出示例（`tables/IrqTable.yaml`）：

```yaml
# IrqTable.yaml
# 从 legacy.xlsx 自动生成，未包含 ref 关联关系。
# 人工校对并补充 ref 块后再提交。

- index:
    vector: 10
  attribute:
    priority: 2
    trigger: edge
    enabled: true
```

### 2. 启动画布

```bash
ecfg serve --port 5000
# 浏览器打开 http://127.0.0.1:5000
```

Phase 0 只有占位页，后续阶段会接入 vis-network 画布。

## 运行测试

```bash
pytest -q
```

## 项目结构

```
src/ecfg/
├── model.py               # Record / Table / CellValue  (layer 0, generic)
├── io/                    # IO 中枢
│   ├── importers/         # Excel / XML / YAML → Table
│   └── exporters/         # Table → YAML / XML / Excel
├── app.py                 # Flask create_app
├── cli.py                 # click CLI 入口
└── templates/

docs/
└── merge-spec.md          # Merge 规则权威规范（AI agent 改 YAML 时照此文档）

examples/
└── tables/
    └── Interrupt.yaml     # 带 TEMPLATE 块的示例表

tests/
├── test_excel_importer.py
└── test_io_roundtrip.py
```

## 相关文档

- `docs/merge-spec.md` — **Merge 规则权威规范**（三区域 + `@` 注释 + 6 种 merge + noconflict_group + 算法 + 举例）
- `examples/tables/Interrupt.yaml` — 带 TEMPLATE 块的示例表，演示所有特性
- `PROMPT.md` — 本项目给弱 AI 的消费入口（prompt 链索引）
- 完整需求与架构：见仓库对话记录中的"ecfg 需求分析"
