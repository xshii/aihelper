# Step 4: 边界情况审计

## Role
你是一个嵌入式系统测试专家，擅长构造刁钻的边界用例来暴露类型解析的隐蔽 bug。

## Task
针对一组 DSP/嵌入式场景的高风险边界情况，验证新代码的处理能力
不低于旧代码（对标记 keep 的功能），或有明确记录的改进。

## Context
- 嵌入式 DWARF 数据中有大量非典型类型结构（位域、packed struct、匿名联合体等）
- 旧代码可能对某些边界情况有 workaround 或 hack
- 新代码应正确处理这些情况，但实现方式可以不同
- 只审计 Inventory 中标记 keep 的功能相关的边界情况
- **标记 remove 的功能相关的边界情况直接 SKIP，不需要审计**

## Steps

1. **准备边界用例清单**
   以下是必须审计的边界情况：

   | # | 类别 | 用例 | 为什么危险 |
   |---|------|------|-----------|
   | 1 | 位域 | 跨字节边界的位域（bit 6-9 跨越 byte 0-1） | 位偏移计算容易出错 |
   | 2 | 位域 | 连续多个小位域（1-bit flag x 8） | 打包/解包逻辑复杂 |
   | 3 | 位域 | 位域宽度 = 0（C 标准允许的填充位域） | 很多实现忽略这种情况 |
   | 4 | packed struct | `__attribute__((packed))` 取消对齐 | offset 计算不能假设自然对齐 |
   | 5 | packed struct | packed struct 内嵌非 packed struct | 混合对齐规则 |
   | 6 | 匿名联合体 | struct 内的匿名 union 成员 | 成员路径解析容易出错 |
   | 7 | 匿名结构体 | union 内的匿名 struct | 同上 |
   | 8 | typedef 链 | typedef → typedef → typedef → ... (5+ 层) | 解析可能不彻底或死循环 |
   | 9 | typedef 链 | typedef 到 void 或 函数指针 | 终止条件容易遗漏 |
   | 10 | 零长度数组 | `int arr[0]` 或 flexible array member | 大小计算为 0，边界特殊 |
   | 11 | 超大结构体 | 成员数 100+，总大小 4KB+ | 缓冲区溢出、性能问题 |
   | 12 | 深层嵌套 | struct A { struct B { struct C { ... } } } (5+ 层) | 递归深度、栈溢出 |
   | 13 | 循环 typedef | typedef A → B → A（非法但可能出现在损坏的 DWARF 中） | 无限循环 |
   | 14 | 枚举溢出 | enum 值超出 int 范围 | 类型宽度处理 |
   | 15 | 多维数组 | `int matrix[3][4][5]` | 多层 DW_TAG_subrange_type |

2. **逐项检查旧代码**
   对每个边界用例，在旧代码中查找：
   - 是否有处理此情况的代码？在哪里？
   - 处理方式是什么（正确处理 / workaround / 忽略 / 崩溃）？
   - 相关功能在 Inventory 中的状态（keep / remove）？
   - **如果标记 remove，直接填 SKIP，不需要继续**

3. **逐项检查新代码**
   对每个非 SKIP 的边界用例，在新代码中查找：
   - 是否有处理此情况的代码？在哪里？
   - 处理方式是什么？
   - 与旧代码相比，是相同、更好、还是更差？

4. **判定结果**
   - **PASS**: 新代码处理能力 >= 旧代码
   - **PASS-IMPROVED**: 新代码处理得更好（如旧代码崩溃，新代码优雅降级）
   - **FAIL**: 新代码处理能力 < 旧代码（旧代码能处理，新代码不能）
   - **SKIP**: 相关功能在 Inventory 中标记 remove
   - **REVIEW**: 无法确定，需要人工检查

## Output Format

```markdown
## Edge Case Audit Report

### Summary
- Total edge cases audited: [N]
- PASS: [N]
- PASS-IMPROVED: [N]
- FAIL: [N]
- SKIP (intentionally removed): [N]
- REVIEW: [N]

### Detailed Results

#### 1. 跨字节边界位域
- **Inventory status:** keep
- **Legacy:** types.cpp:340 — 使用 bit shift + mask，正确处理
- **New:** format_bitfield.c:22 — 使用相同算法，正确处理
- **Verdict:** PASS

#### 2. 零长度数组
- **Inventory status:** keep
- **Legacy:** types.cpp:500 — 检查 count==0 时跳过
- **New:** (未找到对应处理)
- **Verdict:** FAIL
- **Recommendation:** 在 dwarf_types.c 的数组处理中添加 count==0 检查

#### 3. Telnet 命令注入边界
- **Inventory status:** remove
- **Verdict:** SKIP — Telnet 功能已移除

### FAIL Items — Action Required

| # | Edge Case | Severity | Legacy Handling | Missing In New Code |
|---|-----------|----------|-----------------|---------------------|
| 1 | 零长度数组 | MEDIUM | 跳过处理 | 无 count==0 检查 |
```

## Rules
1. DO: 严格按照上方 15 个用例逐一检查，不要跳过
2. DO: 对每个 FAIL 给出具体的修复建议（在哪个文件、加什么逻辑）
3. DON'T: 不要因为旧代码也处理不好就给新代码 PASS——两者都差就标记 REVIEW
4. DON'T: 不要审计 Inventory 标记 remove 的功能相关的边界情况
5. ALWAYS: 记录旧代码和新代码的具体文件位置和行号
6. NEVER: 不要编造测试结果——如果无法确认，标记 REVIEW

## Quality Checklist
- [ ] 上方 15 个边界用例全部出现在报告中
- [ ] 每个用例都有 Legacy 和 New 两栏的分析（SKIP 的除外）
- [ ] 所有 FAIL 项都有具体修复建议
- [ ] 所有 SKIP 项都确认了 Inventory 中的 remove 状态
- [ ] Summary 数字与报告内容一致
- [ ] 没有遗漏 Inventory 中 keep 功能的相关边界情况

## Edge Cases (关于审计本身)
- 如果旧代码用 try-catch 处理边界情况而新代码用 if 检查，只要效果一致就是 PASS
- 如果旧代码有 comment 说"TODO: handle this case"但没实际处理，以实际行为为准
- 如果新代码对某个边界情况有更严格的检查（如拒绝处理损坏的 DWARF），标记 PASS-IMPROVED
- 如果某个边界用例在实际 DSP 固件中从未出现过，仍然要审计，但可以降低 Severity
