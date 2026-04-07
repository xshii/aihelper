# Prompt 架构合规性审查报告

> 审查基准：CLAUDE.md Section 3.1 模板 + 5 大原则
> 审查时间：2026-04-07

## 总评

6 个 prompt 在 Role/Task/Context/Rules/Checklist 方面合格，但存在一个系统性缺陷：
**5/6 缺少 Input → Output 样例**，违反原则 3（样例就是最好的 Prompt）。

## 逐文件评估

| Prompt | Role | Task | Context | Rules | Steps | Output Format | Examples | Checklist | Edge Cases | 得分 |
|--------|:----:|:----:|:-------:|:-----:|:-----:|:------------:|:--------:|:---------:|:----------:|:----:|
| 01-add-codec | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ | 8/9 |
| 02-add-op | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | 7/9 |
| 03-bridge-golden-c | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✓ | 6/9 |
| 04-write-tests | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | ✗ | 6/9 |
| 05-add-dtype | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | 7/9 |
| 06-add-op-convention | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | 7/9 |

## 修补计划

### P0：给每个 prompt 补 Input → Output 样例（原则 3）
- 每个 prompt 补 2-3 个样例：1 典型 + 1 边界/错误
- 样例必须是完整可复制的代码 diff，不是抽象描述

### P1：补齐 Edge Cases 和逃生路径（原则 4）
- 02-add-op：golden_c 缺失时怎么办
- 04-write-tests：conftest fixtures 内联说明
- 05-add-dtype：漏改某个文件时的错误提示
- 06-add-op-convention：何时复用已有 Convention

### P2：统一约束级别（原则 2）
- MUST / SHOULD / NEVER 分级标注
- 03-bridge-golden-c：方式 A/B 加选择标准
- 02-add-op：golden_c 参数标注为 SHOULD（非 MUST）
