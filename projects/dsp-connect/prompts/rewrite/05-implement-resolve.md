# Step 5: 实现符号解析层

## Role
你是一个调试器内核开发者，擅长实现变量路径解析和类型系统遍历。

## Task
实现 `src/resolve/` 下的符号解析层代码。
支持与现有代码相同的路径表达式语法（dot 表示法、数组下标）。

## Context
符号解析层将人类可读的变量路径（如 `"g_config.mode"` 或 `"g_buffer[3].x"`）
转换为具体的内存地址 + 类型信息。

解析过程：
1. 从路径中提取根变量名（如 `"g_config"`）
2. 在符号表中查找根变量 → 得到基地址和类型
3. 逐段解析路径的后续部分（`.mode`、`[3]`、`.x`）
4. 每一段根据当前类型计算偏移量并更新类型

## Refer to Demo
逐一阅读以下文件：
- `src/resolve/resolve.h` — 主接口：`dsc_resolve(symtab, arch, path, out)`
- `src/resolve/resolve.c` — 实现：递归下降路径解析器 + 类型树遍历
- `src/resolve/resolve_cache.h` — 可选的解析缓存
- `src/resolve/resolve_cache.c` — 缓存实现

重点关注：
- `dsc_resolved_t` 结构体：addr + size + type
- 路径解析如何按 `.` 和 `[` 分割
- struct 成员查找如何使用 `dsc_struct_field_t.byte_offset`
- 数组索引如何使用 `element_type` 和 `byte_size`
- typedef/const/volatile 如何透明处理

## Check Inventory
打开 Inventory JSON，确认：
1. 现有代码支持哪些路径表达式语法（keep/remove/uncertain）
2. 是否有超出 demo 支持范围的语法（如指针解引用 `*ptr`、函数调用 `foo()`）
3. 是否有解析缓存需求

## Rules
1. DO: 支持以下路径语法（demo 标准集）：
   - 简单变量：`"g_counter"`
   - struct 成员：`"g_config.mode"`
   - 嵌套成员：`"g_config.network.ip"`
   - 数组索引：`"g_buffer[3]"`
   - 组合路径：`"g_config.items[2].name"`
2. DO: 在解析每一段时解开 typedef/const/volatile（调用 `dsc_type_resolve_typedef`）
3. DO: 使用 arch 的地址转换（struct 偏移可能需要转换）
4. DO: 每个函数不超过 50 行
5. DON'T: 不要支持 demo 中没有的语法（如 `->`, `*`, `&`）
6. DON'T: 不要实现 Inventory 中 `remove` 的路径语法
7. DON'T: 不要在 resolve 层做任何 I/O
8. NEVER: 不要假设路径总是有效的——所有错误路径必须返回明确的错误码
9. ALWAYS: 检查数组越界（索引 >= 数组长度时返回错误）

## Steps

### 5.1 实现路径分词器
将路径字符串分割为 token 序列：

```
"g_config.items[2].name"
→ [ROOT:"g_config", MEMBER:"items", INDEX:2, MEMBER:"name"]
```

实现规则：
- `.` 前的部分是成员名
- `[N]` 是数组索引（N 必须是非负整数）
- 第一个 token 是根变量名
- 空路径、空成员名、负索引都是错误

### 5.2 实现类型遍历器
对每种 token 类型，实现对应的类型遍历逻辑：

| Token 类型 | 当前类型要求 | 计算逻辑 |
|-----------|------------|---------|
| ROOT | - | 在 symtab 中查找 → 得到 addr + type |
| MEMBER | DSC_TYPE_STRUCT 或 DSC_TYPE_UNION | 在 fields 中查找 → addr += field.byte_offset |
| INDEX | DSC_TYPE_ARRAY | addr += index * element_type.byte_size |

每一步都要先解开 typedef：
```c
const dsc_type_t *real = dsc_type_resolve_typedef(current_type);
/* 然后对 real->kind 做 switch */
```

### 5.3 实现 dsc_resolve()
串联分词器和类型遍历器：

```
1. 分词
2. 查找根变量 → addr, type
3. for each remaining token:
     resolve_typedef(type)
     switch (token.kind):
       MEMBER → find_field(type, token.name) → update addr, type
       INDEX  → check_bounds(type, token.index) → update addr, type
4. 填充 dsc_resolved_t: addr, size=type.byte_size, type
```

### 5.4 实现 resolve_cache（可选）
如果 Inventory 表明解析缓存有价值（高频变量查询场景）：
- 用 hashmap 缓存：key = path string, value = dsc_resolved_t
- 提供 invalidate 函数（ELF reload 时清空）
- 实现 `dsc_resolve_cached()` 包装函数

### 5.5 处理现有代码的特殊语法
如果现有代码支持 demo 之外的路径语法（从 Inventory 获取）：
- 标记为 `keep` 的：尽量实现，但不破坏 demo 的接口
- 标记为 `remove` 的：跳过
- 标记为 `uncertain` 的：标记 `[NEEDS_HUMAN_REVIEW]`

## Output Format
产出以下文件：
- `resolve.c` — 主解析逻辑
- `resolve_cache.c` — 缓存实现（如果需要）

每个文件顶部：
```c
/* PURPOSE: [描述]
 * PATTERN: 递归下降路径解析器 + 类型树遍历
 * FOR: 弱 AI 参考如何将 "g_config.mode" 解析为 {addr, size, type} */
```

## Quality Checklist
- [ ] 5 种路径形式全部支持：简单变量、struct 成员、嵌套成员、数组索引、组合
- [ ] typedef/const/volatile 在每一步都正确解开
- [ ] 数组越界检查：索引 >= count 时返回 `DSC_ERR_INVALID_ARG`
- [ ] 成员不存在时返回明确的错误码
- [ ] 根变量不存在时返回明确的错误码
- [ ] 空路径 / NULL 路径返回 `DSC_ERR_INVALID_ARG`
- [ ] 每个函数不超过 50 行
- [ ] union 成员访问正确处理（offset 可能是 0）
- [ ] Inventory 中 `remove` 的语法没有实现
- [ ] 缓存 invalidate 在 reload 场景下可用

## Edge Cases
- 如果 struct 有匿名嵌套 struct（如 `struct { struct { int x; }; int y; }`），
  匿名成员的 byte_offset 直接用——不需要名称匹配
- 如果数组是 flexible array（count = 0），允许任意索引但在注释中标注
- 如果 union 成员访问，所有成员的 byte_offset 都是 0——返回指定成员的类型
- 如果路径有连续的下标 `a[1][2]`（多维数组），逐维处理

## When Unsure
- **不确定某种路径语法是否需要？** 查 Inventory。demo 标准集 5 种一定要支持
- **不确定偏移量计算是否正确？** 写一个注释说明公式：`new_addr = base_addr + field.byte_offset`
- **不确定 typedef 链是否处理完全？** 用 while 循环解开，直到 kind 不再是 TYPEDEF/CONST/VOLATILE
- **遇到现有代码支持的复杂语法？** 标记 `[NEEDS_HUMAN_REVIEW]`，不要尝试实现
