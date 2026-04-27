# ai-restble — Prompt 链索引

> 给弱 AI 的消费入口。强 AI 把每个阶段的设计和编码任务写成 prompt，弱 AI 按 prompt 执行或扩展。

## 当前状态

**Phase 0 骨架完成**。以下为计划中的 prompt 链，按执行顺序排列。

## Phase 0：骨架与 Excel 导入（已完成）

> 本阶段的 prompt 尚未抽取为独立文件。参考产物：
> - `src/ecfg/cli.py` — CLI 框架
> - `src/ecfg/app.py` — Flask create_app
> - `src/ecfg/importers/excel.py` — sheet → YAML 表文件
> - `tests/test_excel_importer.py` — round-trip 单测

**产出清单**：
- [x] `ecfg --help` 可列出 `validate / expand / serve / import-excel` 命令
- [x] `ecfg serve` 启动 Bootstrap 占位页
- [x] `ecfg import-excel foo.xlsx` 生成符合三区域规范的 YAML

## Phase 1：后端核心（规则已定稿，待实现）

**权威规范**：
- `docs/yaml-schema.md`（**必读** — XML ↔ YAML round-trip 协议、注解全集、文件命名）
- `docs/merge-spec.md`（多 team 融合：merge 策略、TEMPLATE 块）

**Skill 实现 prompt**（用于实现 skill 的弱 AI）：
- `prompts/skill-preprocess.md` — XML → YAML 拆解
- `prompts/skill-postprocess.md` — YAML → XML 字节级稳定合成

**参考 fixture**：`tests/fixtures/xml/valid/{multi_runmode,minimal,empty_table,hex_widths}.expected/`（schema 落地实例）
**合规测试**：`tests/test_yaml_schema_compliance.py`（验证 fixture 符合 yaml-schema.md；含 xfail 占位的 byte-level round-trip）
**示例表**：`examples/tables/Interrupt.yaml`（演示 TEMPLATE + 6 种 merge + ref）

计划拆分为以下 prompt：

- `prompts/phase1/01-template-parser.md`   — TEMPLATE BEGIN/END 块解析（注释转 YAML）
- `prompts/phase1/02-annotation-parser.md` — `@merge: concat(',')` / `@range` / `@enum` mini-parser
- `prompts/phase1/03-schema-loader.md`     — 从 TEMPLATE + 注释合成内存 schema 对象
- `prompts/phase1/04-policies.md`          — 6 种 merge rule 实现（concat/sum/max/min/union/conflict）
- `prompts/phase1/05-merger.md`            — 多 team 融合引擎（merge-spec §5 算法）
- `prompts/phase1/06-validator.md`         — schema 加载期 + 运行期校验（含 noconflict_group 对称）

每条 prompt 独立可执行，包含角色、背景、规则、步骤、样例、自检清单。

## Phase 2：可视化只读（待做）

- `prompts/phase2/01-graph-builder.md`  — 节点图 JSON
- `prompts/phase2/02-vis-network.md`    — 前端 vis-network 集成
- `prompts/phase2/03-detail-panel.md`   — 右栏详情面板

## Phase 3：记录编辑（待做）

- `prompts/phase3/01-record-crud.md`    — 表单编辑 + YAML 写回
- `prompts/phase3/02-schema-form.md`    — 按 schema 生成表单

## Phase 4+：导出、ref 编辑（待做）

## 使用建议

- **弱 AI 执行**：打开对应 prompt 文件，复制其中的 "Task / Rules / Steps / Examples"，按自检清单交付
- **人类审阅**：每条 prompt 都带 "Quality Checklist"，审阅时逐项检查
- **扩展**：在 `prompts/phase*/` 下增加新文件，同步更新本索引
