# Step 2: 实现 DWARF 解析层

## Role
你是一个 DWARF 调试信息解析专家，熟悉 libdwarf API 和 ELF 文件格式。

## Task
实现 `src/dwarf/` 下的所有文件，使用 **libdwarf** 作为底层库。
只实现 Inventory 中标记为 `keep` 的 DWARF 功能。

## Context
现有 C++ 代码可能自己实现了 DWARF 解析（"造轮子"）。在重写中，我们统一使用 libdwarf 库。
如果现有代码有 libdwarf 不支持的自定义 DWARF 特性，不要尝试实现——记录为扩展点。

dsp-connect demo 的 DWARF 层负责：
- 打开 ELF 文件，初始化 DWARF 解析器
- 提取全局变量符号（名称 → 地址 + 类型）
- 构建类型树（struct/enum/array/pointer/typedef/base）
- 可选：行号映射、栈帧信息

## Refer to Demo
逐一阅读以下文件，理解接口和实现模式：
- `src/dwarf/dwarf_parser.h` — 解析器主接口：open/close/load_symbols/lookup_type
- `src/dwarf/dwarf_parser.c` — 实现参考（如果存在）
- `src/dwarf/dwarf_types.h` — 类型系统：tagged union `dsc_type_t`，X-macro 枚举
- `src/dwarf/dwarf_types.c` — 类型工具函数：dsc_type_size, dsc_type_resolve_typedef
- `src/dwarf/dwarf_symbols.h` — 符号表：dsc_symtab_t，add/lookup/iterate
- `src/dwarf/dwarf_symbols.c` — 符号表实现
- `src/dwarf/dwarf_lines.h` / `dwarf_frames.h` — 可选功能

## Check Inventory
打开 Inventory JSON，定位 `dwarf_parser` 模块：
1. 列出所有 `status: "keep"` 的 features — 这些你必须实现
2. 列出所有 `status: "remove"` 的 features — 跳过，不写代码
3. 列出所有 `status: "uncertain"` 的 features — 标记 `[NEEDS_HUMAN_REVIEW]`
4. 特别关注：lines 和 frames 是否标记为 keep

## Rules
1. DO: 使用 libdwarf API（`dwarf_init_path`, `dwarf_siblingof_b`, `dwarf_child` 等）
2. DO: 将现有代码的类型处理逻辑映射到 `dsc_type_t` tagged union
3. DO: 每个函数不超过 50 行——DWARF 遍历逻辑很容易变长，必须拆分
4. DO: 处理所有 `dsc_type_kind_t` 中列出的类型种类
5. DON'T: 不要自己解析 `.debug_*` section 的二进制格式
6. DON'T: 不要实现 Inventory 中 `remove` 的功能
7. DON'T: 不要修改 `dwarf_types.h` 和 `dwarf_symbols.h` 中的类型定义
8. NEVER: 不要猜测现有代码中的自定义 DWARF 特性如何工作——记录为扩展点
9. ALWAYS: 对每个 DWARF DIE tag 的处理，添加注释说明对应的 DW_TAG_xxx

## Steps

### 2.1 实现 dwarf_types.c
1. 实现 `dsc_type_kind_name()` — 用 X-macro 展开
2. 实现 `dsc_base_encoding_name()` — 用 X-macro 展开
3. 实现 `dsc_type_size()` — 读 `byte_size`，对 typedef 递归跟踪
4. 实现 `dsc_type_resolve_typedef()` — 解开 typedef/const/volatile 链
5. 实现 `dsc_type_free()` — 释放 owned 数组和字符串，不释放 borrowed 指针

### 2.2 实现 dwarf_symbols.c
1. 实现 `dsc_symtab_init()` — 零初始化
2. 实现 `dsc_symtab_add()` — 动态数组追加 + hashmap 索引更新
3. 实现 `dsc_symtab_lookup()` — hashmap O(1) 查找
4. 实现 `dsc_symtab_at()` / `dsc_symtab_count()` — 简单访问器
5. 实现 `dsc_symtab_free()` — 释放所有 symbol name 和内部索引

### 2.3 实现 dwarf_parser.c（核心）
1. **dsc_dwarf_open**: 用 `dwarf_init_path()` 打开 ELF，初始化内部状态
2. **dsc_dwarf_close**: 释放 libdwarf handle，释放所有 owned 类型
3. **dsc_dwarf_load_symbols**: 遍历所有 CU → 遍历所有 DIE → 提取 DW_TAG_variable
   - 对每个变量：提取名称(DW_AT_name)、地址(DW_AT_location)、类型引用(DW_AT_type)
   - 地址提取：处理 DW_OP_addr 位置表达式
   - 类型提取：递归解析 DW_AT_type 引用的 DIE
4. **dsc_dwarf_lookup_type**: 用 DIE offset 查找已解析的类型

### 2.4 类型解析核心逻辑
为每种 `dsc_type_kind_t` 实现从 DWARF DIE 到 `dsc_type_t` 的转换：

| DW_TAG | dsc_type_kind_t | 要提取的属性 |
|--------|-----------------|-------------|
| DW_TAG_base_type | DSC_TYPE_BASE | DW_AT_encoding, DW_AT_byte_size |
| DW_TAG_structure_type | DSC_TYPE_STRUCT | DW_AT_member (递归) |
| DW_TAG_union_type | DSC_TYPE_UNION | DW_AT_member (递归) |
| DW_TAG_enumeration_type | DSC_TYPE_ENUM | DW_AT_enumerator |
| DW_TAG_array_type | DSC_TYPE_ARRAY | DW_AT_subrange_type |
| DW_TAG_pointer_type | DSC_TYPE_POINTER | DW_AT_type |
| DW_TAG_typedef | DSC_TYPE_TYPEDEF | DW_AT_type |
| DW_TAG_const_type | DSC_TYPE_CONST | DW_AT_type |
| DW_TAG_volatile_type | DSC_TYPE_VOLATILE | DW_AT_type |
| DW_TAG_subroutine_type | DSC_TYPE_FUNC | DW_AT_type + params |

- 每种类型的解析拆分为独立的 `parse_xxx_type()` helper 函数
- 用 hashmap 缓存已解析的类型（key = DIE offset），避免重复解析

### 2.5 可选：实现 dwarf_lines.c / dwarf_frames.c
**只有 Inventory 中明确标记为 `keep` 时才实现。** 否则创建空桩文件。

## Output Format
每个文件的完整 C 源码，格式：

```c
/* PURPOSE: [描述]
 * PATTERN: [使用的设计模式]
 * FOR: [弱 AI 参考时的关注点] */

#include "xxx.h"
// ... implementation
```

对于跳过的功能，在文件中添加注释：

```c
/* SKIPPED: [功能名] — Inventory status: remove
 * Reason: [从 Inventory 复制删除理由] */
```

对于 uncertain 的功能：

```c
/* [NEEDS_HUMAN_REVIEW]: [功能名] — Inventory status: uncertain
 * Question: [从 Inventory 复制需要确认的问题] */
```

## Quality Checklist
- [ ] 所有 `dsc_type_kind_t` 中列出的类型都有对应的解析代码（或 SKIPPED 注释）
- [ ] `dsc_dwarf_load_symbols` 能正确遍历 CU 和 DIE
- [ ] 每个函数不超过 50 行
- [ ] 类型缓存使用 DIE offset 作为 key
- [ ] 所有 libdwarf 调用有错误检查
- [ ] Inventory 中 `remove` 的功能没有实现代码
- [ ] Inventory 中 `uncertain` 的功能有 `[NEEDS_HUMAN_REVIEW]` 标记
- [ ] 所有 owned 内存在 close/free 时正确释放
- [ ] 没有从 demo 的 `dwarf_types.h` / `dwarf_symbols.h` 修改任何类型定义

## Edge Cases
- 如果现有代码处理了 DW_TAG_variable 的 DW_OP_fbreg（栈上变量），跳过——软调只关注全局变量
- 如果现有代码有自定义 DW_AT 属性（vendor extension），记录为扩展点，不实现
- 如果 libdwarf API 与现有代码的自造轮子在行为上有差异，以 libdwarf 为准
- 如果遇到匿名 struct/union（name == NULL），正常处理——dsc_type_t 允许 name 为 NULL

## When Unsure
- **不确定某个 DW_TAG 是否需要处理？** 查 Inventory。如果 Inventory 没有提到，跳过并标记 `[NEEDS_HUMAN_REVIEW]`
- **不确定 libdwarf API 怎么用？** 使用最基本的遍历模式：`dwarf_next_cu_header_d` → `dwarf_siblingof_b` → `dwarf_child`
- **不确定类型映射是否正确？** 写一个注释说明你的映射逻辑，让人类审查
- **遇到现有代码中看不懂的 DWARF 处理？** 不要猜——标记 `[NEEDS_HUMAN_REVIEW]` 并附上原始代码位置
