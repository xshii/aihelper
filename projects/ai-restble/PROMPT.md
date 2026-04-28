# ai-restble — Prompt 链索引

> 给弱 AI 的消费入口。强 AI 把每阶段的设计/编码任务写成 prompt，弱 AI 按 prompt 执行或扩展。

## 当前状态

- **Phase 0 骨架**：CLI / Flask 占位画布 / Excel importer ✅
- **Phase 1 schema engine**：annotation parser / TEMPLATE 块 loader / 6 种 merge op /
  validator / merger ✅
- **Legacy XML round-trip**：unpack / pack / 字节级一致 / 多 XML 合一 / @use 跨目录 ref
  / scaffold 生成 ✅
- **可视化**：Phase 2 待做（vis-network 集成）
- **记录编辑**：Phase 3 待做

## 权威规范（必读）

| 文档 | 描述 |
|------|------|
| `docs/yaml-schema.md` | Legacy XML ↔ YAML round-trip 协议；R1-R11 规则 + 注解全集 + 文件命名 + 目录布局 |
| `docs/merge-spec.md` | 多 team yaml 融合引擎；TEMPLATE 块 + 三区域 record + 6 种 merge op |
| `docs/design-completeness.md` | 形式化论证（编译语言视角）+ 可扩展性分析 + TODO 路线图 |

## Skill 实现 prompts（已落地）

每个 skill 是一份独立、可复制粘贴给弱 AI 的实现指引（含 Role/Task/Rules/Steps/Examples/
Checklist/Edge Cases）：

| Skill | 文件 | 对应模块 |
|-------|------|----------|
| **XML → YAML 拆解** | `prompts/skill-preprocess.md` | `ecfg.legacy.preprocess` |
| **YAML → XML 字节级合成** | `prompts/skill-postprocess.md` | `ecfg.legacy.postprocess` |
| **XML → schema scaffold 生成** | `prompts/skill-scaffold.md` | `ecfg.legacy.scaffold` |

参考 fixture：`tests/fixtures/xml/valid/{minimal,empty_table,hex_widths,multi_runmode}.expected/`
（四种复杂度梯度：无 scope/空 wrapper/hex 宽度保留/多 RunMode 完整体）。

合规测试：`tests/test_yaml_schema_compliance.py`（fixture 静态合规 + 字节级 round-trip
+ folder identity + 多 XML + scaffold + 7 类异常路径）。

## Phase 1 schema engine 内部 prompt（计划，未拆出独立文件）

实现已落地（见 `src/ecfg/schema/` + `merge/`），未来如需让弱 AI 重写或扩展某个子模块，
可按以下方式拆分：

- `prompts/phase1/01-annotation-parser.md` — `@key:value` mini-parser（已在
  `ecfg/schema/annotations.py`）
- `prompts/phase1/02-template-block-loader.md` — TEMPLATE BEGIN/END 块解析
- `prompts/phase1/03-schema-loader.md` — 注解 → `FieldSchema` / `TableSchema`
- `prompts/phase1/04-merge-policies.md` — 6 种 merge rule 实现
- `prompts/phase1/05-merger.md` — 多 team 合并引擎
- `prompts/phase1/06-validator.md` — 约束校验

## Phase 2+：待做

- `prompts/phase2/01-graph-builder.md` — 节点图 JSON
- `prompts/phase2/02-vis-network.md` — 前端 vis-network
- `prompts/phase2/03-detail-panel.md` — 右栏详情
- `prompts/phase3/01-record-crud.md` — 表单编辑 + YAML 写回
- `prompts/phase3/02-schema-form.md` — 按 schema 生成表单

## 给弱 AI 的使用建议

1. **读权威文档**：先看 `docs/yaml-schema.md` 弄清协议，再翻 `docs/design-completeness.md`
   理解整体架构
2. **执行 skill**：复制对应 `prompts/skill-*.md` 的"Task / Rules / Steps / Examples"
   到对话；按 Quality Checklist 自检
3. **扩展**：在 `prompts/phaseN/` 下新增 prompt 文件，本索引同步加链接
4. **fixture 是 ground truth**：实现完跑 `pytest tests/test_yaml_schema_compliance.py`
   绿了才算对
