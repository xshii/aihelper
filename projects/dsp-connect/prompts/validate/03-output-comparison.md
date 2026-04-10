# Step 3: 格式化输出对比

## Role
你是一个测试工程师，擅长设计对比测试用例并精确分析输出差异。

## Task
选取一组测试变量，分别用旧代码和新代码读取并格式化输出，对比结果。
区分**可接受差异**和**不可接受差异**，生成逐项 diff 报告。

## Context
- 两套代码都能从 ELF 文件中读取 DWARF 信息并格式化变量值
- 输出格式可能略有不同（空白、大小写、字段顺序），这是可接受的
- 值错误、字段缺失、类型解释错误是不可接受的
- 只测试 Inventory 中标记 `keep` 的功能所涉及的变量类型

## Steps

1. **设计测试变量集**
   至少覆盖以下类型，每类至少 1 个变量：

   | 类别 | 测试变量示例 | 预期输出特征 |
   |------|-------------|-------------|
   | 基本整数 | `int32_t counter` | 十进制或十六进制数值 |
   | 无符号整数 | `uint16_t flags` | 非负数值 |
   | 浮点数 | `float temperature` | 带小数点的数值 |
   | 枚举 | `enum State state` | 枚举名称或数值 |
   | 简单结构体 | `struct Point {x, y}` | 字段名 + 值 |
   | 嵌套结构体 | `struct Config { struct Sub inner; }` | 多层缩进 |
   | 数组 | `int32_t buffer[16]` | 多元素列表 |
   | 指针 | `int32_t *ptr` | 地址值 |
   | typedef | `typedef uint32_t Handle; Handle h;` | 解析到底层类型 |
   | 位域 | `struct { uint32_t flag:1; }` | 位域值 |

2. **运行旧代码获取输出**
   对每个测试变量，记录旧代码的完整格式化输出。
   如果无法运行旧代码，从旧代码的测试用例或文档中提取预期输出。

3. **运行新代码获取输出**
   对相同的测试变量，记录新代码的完整格式化输出。
   使用 `src/` 目录下的 demo 代码或测试代码。

4. **逐项 diff 分析**
   对每个变量的输出对：
   - 逐行对比
   - 对每个差异点判定为可接受或不可接受

   **可接受差异：** 空白差异、hex 大小写（`0xAB` vs `0xab`）、hex 前缀风格、
   字段输出顺序（只要都在）、额外诊断信息、数组截断阈值不同、新代码多输出有用信息。

   **不可接受差异：** 数值错误、字段名错误或缺失、类型解释错误（signed/unsigned 混淆、
   float 当 int）、结构体成员完全缺失、数组大小错误、枚举值→名称映射错误。

5. **汇总 diff 结果**

## Output Format

```markdown
## Output Comparison Report

### Summary
- Total test variables: [N]
- PASS (identical or acceptable diff): [N]
- FAIL (unacceptable diff): [N]
- SKIP (type not supported / intentionally removed): [N]

### Detailed Comparison

#### Variable 1: `int32_t counter`
- **Type category:** 基本整数
- **Legacy output:**
  ```
  counter = 42 (0x0000002A)
  ```
- **New output:**
  ```
  counter = 42 (0x2a)
  ```
- **Diff:** hex 大小写差异
- **Verdict:** PASS (可接受差异)

#### Variable 2: `struct Point point`
- **Type category:** 简单结构体
- **Legacy output:**
  ```
  point.x = 10
  point.y = 20
  ```
- **New output:**
  ```
  point = { x = 10, y = 20 }
  ```
- **Diff:** 格式化方式不同，但所有字段和值都正确
- **Verdict:** PASS (可接受差异)

### FAIL Items — Action Required

| # | Variable | Type | Diff Description | Severity |
|---|----------|------|-----------------|----------|
| 1 | `flags` | bitfield | 位域值解析错误 | HIGH |
```

## Rules
1. DO: 每种类型至少测试一个变量
2. DO: 对每个 diff 明确判定可接受/不可接受，并引用上方清单中的条目
3. DON'T: 不要只看输出"像不像"——要逐字段验证值的正确性
4. DON'T: 不要测试 Inventory 中标记 remove 的功能涉及的变量类型
5. ALWAYS: 保留完整的输入和输出记录，便于复现
6. NEVER: 不要因为格式不同就判 FAIL——先确认值是否正确

## Quality Checklist
- [ ] 至少 10 个测试变量，覆盖上述所有类型类别
- [ ] 每个变量都有完整的旧输出和新输出
- [ ] 每个差异都明确分类为可接受或不可接受
- [ ] 可接受差异引用了具体的可接受条目
- [ ] 不可接受差异有明确的修复建议
- [ ] Summary 数字准确

## Edge Cases
- 如果无法运行旧代码，从测试用例或文档推导预期输出，并在报告中注明"预期输出来源"
- 如果某个变量在旧代码中会崩溃/报错，但新代码正确处理了，标记为 PASS-IMPROVED
- 如果新代码输出了旧代码没有的额外字段，只要旧字段都在且正确，判 PASS
- 如果不确定某个差异是否可接受，标记为 REVIEW 并附上你的判断理由
