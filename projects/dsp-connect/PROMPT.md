# dsp-connect Prompt 索引

本文件是所有 prompt 链的入口。根据你要做的事情，选择对应的链。

## 选择指南

```
你想做什么？
│
├─ 理解现有代码（重写前）
│  → prompts/discover/   「盘点」链
│
├─ 按 demo 重写代码
│  → prompts/rewrite/    「重写」链
│
├─ 验证新旧代码一致性
│  → prompts/validate/   「验证」链
│
└─ 给新架构/协议做适配
   → prompts/adapt/      「适配」链
```

## 推荐工作流

```
1. discover（盘点）→ 产出功能清单 inventory.json
2. rewrite（重写） → 按 inventory 逐层实现，跳过标记为 remove 的功能
3. validate（验证）→ 对比新旧输出，确认行为一致
4. 如有新硬件 → adapt（适配）→ 添加新的 arch/transport 适配器
```

## Prompt 链详情

### 1. Discover — 盘点现有代码 (`prompts/discover/`)

**目标：** 在重写前彻底理解现有代码，产出结构化功能清单。

| 步骤 | 文件 | 做什么 |
|------|------|--------|
| 0 | 00-overview.md | 链概览 |
| 1 | 01-find-entry-points.md | 找入口函数和 API |
| 2 | 02-extract-dwarf-usage.md | 盘点 DWARF 功能 |
| 3 | 03-map-transport-layer.md | 盘点通信层 |
| 4 | 04-catalog-type-handling.md | 盘点类型处理 |
| 5 | 05-identify-arch-specifics.md | 盘点架构代码 |
| 6 | 06-identify-dead-code.md | 识别废弃功能 |
| 7 | 07-inventory-report.md | 输出功能清单 JSON |

**⚠️ 核心原则：不是所有功能都需要保留。** Step 6 专门识别多余功能。

### 2. Rewrite — 按 demo 重写 (`prompts/rewrite/`)

**目标：** 参照 `src/` 目录的 demo 代码，逐层重写现有 C++ 代码为 C。

| 步骤 | 文件 | 参照 demo 代码 |
|------|------|---------------|
| 0 | 00-overview.md | — |
| 1 | 01-scaffold-project.md | src/ 目录结构 |
| 2 | 02-implement-dwarf-layer.md | src/dwarf/ |
| 3 | 03-implement-transport.md | src/transport/ |
| 4 | 04-implement-arch.md | src/arch/ |
| 5 | 05-implement-resolve.md | src/resolve/ |
| 6 | 06-implement-memory.md | src/memory/ |
| 7 | 07-implement-format.md | src/format/ |
| 8 | 08-implement-core.md | src/core/ |
| 9 | 09-integration-test.md | tests/ |

**⚠️ 每步都要检查 inventory：只重写 keep，跳过 remove，标记 uncertain。**

### 3. Validate — 验证新旧一致 (`prompts/validate/`)

**目标：** 对比新旧实现，确认行为等价（不是代码等价）。

| 步骤 | 文件 | 做什么 |
|------|------|--------|
| 0 | 00-overview.md | 链概览 |
| 1 | 01-api-surface-diff.md | API 表面对比 |
| 2 | 02-type-coverage-check.md | 类型覆盖矩阵 |
| 3 | 03-output-comparison.md | 输出结果对比 |
| 4 | 04-edge-case-audit.md | 边界情况审计 |
| 5 | 05-validation-report.md | 验证报告 |

**⚠️ 被 inventory 标记为 remove 的功能不应标为"缺失"。**

### 4. Adapt — 适配新架构 (`prompts/adapt/`)

**目标：** 为新的目标芯片或通信协议添加适配器。

| 步骤 | 文件 | 做什么 |
|------|------|--------|
| 0 | 00-overview.md | 链概览 |
| 1 | 01-identify-differences.md | 分析新目标差异 |
| 2 | 02-implement-arch-adapter.md | 实现架构适配器 |
| 3 | 03-implement-transport.md | 实现传输适配器 |
| 4 | 04-register-in-factory.md | 注册到工厂 |
| 5 | 05-test-new-adapter.md | 编写适配器测试 |
| — | adapter-checklist.md | 适配器完整检查表 |

## Demo 代码参考

`src/` 目录是完整的 C 参考实现：

```
src/
├── util/        → 基础设施（hashmap, strbuf, log, dsc_common.h）
├── dwarf/       → DWARF 解析（parser, types, symbols, lines, frames）
├── transport/   → 传输层（vtable + factory + telnet/serial/shm）
├── arch/        → 架构适配（vtable + factory + byte/word addressed）
├── resolve/     → 符号解析（路径表达式 → 地址+类型）
├── memory/      → 内存读写（地址转换 + 分块传输）
├── format/      → 格式化显示（struct/enum/array/primitive）
└── core/        → 胶水层（dsc_open/close/read_var）
```
