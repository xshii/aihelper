# prompts/

Skill 实现 prompt 集合。每份 prompt 是给弱 AI 的独立任务包（含 Role/Task/Context/
Rules/Steps/Output/Examples/Checklist/Edge Cases），符合仓库 `CLAUDE.md` §3.1 的
PROMPT.md 模板。

## 已落地 skill

| Skill | 文件 | 实现位置 | 一句话描述 |
|-------|------|---------|------------|
| **preprocess** | `skill-preprocess.md` | `src/ecfg/legacy/preprocess.py` | Legacy XML → YAML 文件树（多 XML 幂等去重合一） |
| **postprocess** | `skill-postprocess.md` | `src/ecfg/legacy/postprocess.py` | YAML 文件树 → Legacy XML（字节级稳定） |
| **scaffold** | `skill-scaffold.md` | `src/ecfg/legacy/scaffold.py` | 从 XML 抽字段集生成 `template/<scope>/<E>.yaml` schema 占位（无约束注解） |

三个 skill 互相独立：
- preprocess 与 postprocess 是**字节级互逆**（``pack(unpack(xml)) == xml``）
- scaffold 跟主流程**解耦** — 不在 unpack 里触发，按需调用

## 计划中 skill（未拆出独立文件）

Phase 1 schema engine 已实现（`src/ecfg/{schema,merge}/`），未来要让弱 AI 重写或扩展时可拆：

```
prompts/
├── phase1/
│   ├── 01-annotation-parser.md   ← @key:value mini-parser
│   ├── 02-template-block-loader.md
│   ├── 03-schema-loader.md
│   ├── 04-merge-policies.md      ← 6 种 op 实现
│   ├── 05-merger.md              ← 多 team 合并引擎
│   └── 06-validator.md           ← 约束校验
├── phase2/                       ← 可视化（vis-network）
└── phase3/                       ← 记录编辑
```

## 每份 skill 的标准结构

```
# Skill: <名称>
## Role        ← 谁实现这个 skill
## Task        ← 一句话任务描述
## Context     ← 必读权威文档 + 参考 fixture
## Rules       ← 表格形式的硬约束（编号同 yaml-schema.md 便于对照）
## Steps       ← Mermaid 流程图 + 编号步骤
## Output Format
## Examples    ← 至少 3 个：典型 / 边界 / 错误
## Quality Checklist  ← 完成自检
## Edge Cases  ← 已知边界情况的处理决策
## 解决冲突的兜底原则  ← 设计哲学
```

## 给弱 AI 的工作流

1. **读权威**：先看 `docs/yaml-schema.md` + `docs/design-completeness.md`
2. **打开 skill prompt**：复制 Task/Rules/Steps/Examples 到对话
3. **跑测试验证**：`pytest tests/test_yaml_schema_compliance.py` 必须 215 全绿
4. **逐项核 Checklist**：每条打 ✓ 才算交付
5. **遇歧义**：按 skill 末尾的"解决冲突的兜底原则"决策；不静默猜测，不引入未经文档
   背书的注解
