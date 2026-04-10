# Step 4: 实现架构适配层

## Role
你是一个嵌入式系统架构专家，熟悉 DSP 处理器的内存模型（字节寻址 vs 字寻址、大小端）。

## Task
实现 `src/arch/` 下的架构适配层代码。
使用 discover chain Step 5（identify-arch-specifics）中发现的架构参数，替换现有代码中的硬编码魔数。

## Context
DSP 处理器的内存模型多样：
- 有些是字节寻址（和 x86 一样）
- 有些是字寻址（一个地址对应一个 16/24/32 位的字，不是一个字节）
- 字节序可能是大端或小端

架构适配层的职责是：
1. 逻辑地址（DWARF 中的地址） ↔ 物理地址（传输层使用的地址）转换
2. 字节序交换
3. 提供最小访问单元和字大小

demo 使用和传输层相同的 vtable 模式。

## Refer to Demo
逐一阅读以下文件：
- `src/arch/arch.h` — vtable 定义：`dsc_arch_ops`（logical_to_physical/physical_to_logical/swap_endian/min_access_size/word_size/destroy）
- `src/arch/arch_factory.h` — 工厂注册模式
- `src/arch/arch_factory.c` — 工厂实现 + `dsc_arch_register_builtins()`
- `src/arch/arch_byte_addressed.h` / `.c` — 字节寻址实现
- `src/arch/arch_word_addressed.h` / `.c` — 字寻址实现

重点关注：
- `dsc_arch_config_t` 的三个参数：`word_bits`, `is_big_endian`, `addr_shift`
- 字节寻址 vs 字寻址的地址转换公式
- 字节序交换的实现方式

## Check Inventory
打开 Inventory JSON，定位架构相关模块：
1. 确认 discover chain Step 5 中记录的目标架构参数：
   - 字大小（word_bits）
   - 字节序（big/little endian）
   - 地址偏移（addr_shift）
   - 任何硬编码的魔数
2. 确认哪些架构 backend 标记为 `keep`
3. 确认哪些标记为 `remove`

## Rules
1. DO: 每个具体 arch struct 的第一个成员必须是 `dsc_arch_t`
2. DO: 将 discover chain Step 5 中发现的硬编码魔数转换为 `dsc_arch_config_t` 参数
3. DO: 每个函数不超过 50 行
4. DO: 实现 `dsc_arch_register_builtins()` 注册所有 keep 的 backend
5. DON'T: 不要修改 `arch.h` 中的 vtable 定义
6. DON'T: 不要实现 Inventory 中 `remove` 的 backend
7. DON'T: 不要在 arch 层做任何 I/O 操作——这是纯计算层
8. NEVER: 不要硬编码地址偏移量或字大小——必须通过 config 传入
9. ALWAYS: 在地址转换中处理溢出（地址超过 64 位范围）

## Steps

### 4.1 实现 arch_factory.c
1. 定义静态注册表（名称 + 创建函数指针）
2. 实现 `dsc_arch_register()` — 添加到注册表
3. 实现 `dsc_arch_create()` — 按名称查找并调用创建函数
4. 实现 `dsc_arch_register_builtins()` — 注册所有内置 backend

### 4.2 实现字节寻址 backend（arch_byte_addressed.c）
适用于传统字节寻址处理器（如 ARM Cortex）：

```c
typedef struct {
    dsc_arch_t       base;          /* MUST be first member */
    int              is_big_endian;
} byte_addressed_arch_t;
```

vtable 实现：
| 函数 | 字节寻址行为 |
|------|------------|
| `logical_to_physical` | 直接映射：physical = logical（字节寻址无需转换） |
| `physical_to_logical` | 直接映射：logical = physical |
| `swap_endian` | 如果 host 和 target 端序不同，反转字节 |
| `min_access_size` | 返回 1（字节） |
| `word_size` | 返回 config.word_bits / 8 |

### 4.3 实现字寻址 backend（arch_word_addressed.c）
适用于 DSP 处理器（如 TI C5x/C6x、CEVA）：

```c
typedef struct {
    dsc_arch_t       base;
    int              word_bits;
    int              is_big_endian;
    int              addr_shift;
} word_addressed_arch_t;
```

vtable 实现：
| 函数 | 字寻址行为 |
|------|----------|
| `logical_to_physical` | physical = logical >> addr_shift（或其他转换公式） |
| `physical_to_logical` | logical = physical << addr_shift |
| `swap_endian` | 按 word_bits/8 的字大小反转 |
| `min_access_size` | 返回 word_bits / 8 |
| `word_size` | 返回 word_bits / 8 |

**关键：** 地址转换公式必须来自 discover chain Step 5，不要猜测。
如果现有代码中有类似 `addr * 2` 或 `addr << 1` 的操作，那就是地址转换逻辑。

### 4.4 替换魔数
检查 discover chain Step 5 输出中列出的所有硬编码魔数：

| 现有代码中的魔数 | 转换为 |
|----------------|--------|
| `* 2` 或 `<< 1` | `addr_shift = 1` |
| `0xFF` mask | `word_bits = 8` |
| `0xFFFF` mask | `word_bits = 16` |
| `0xFFFFFF` mask | `word_bits = 24` |
| byte swap `(x >> 8) \| (x << 8)` | `is_big_endian = 1` (或 0) |

将这些全部参数化到 `dsc_arch_config_t` 中。

## Output Format
每个 backend 产出 `.h` + `.c` 两个文件，加上工厂实现。

文件头注释格式：
```c
/* PURPOSE: [架构名] backend — [寻址方式]，[字节序]
 * PATTERN: vtable 实现 — 嵌入 dsc_arch_t 作为第一个成员
 * FOR: 弱 AI 参考如何添加新的架构 backend */
```

## Quality Checklist
- [ ] 每个具体 arch struct 的第一个成员是 `dsc_arch_t`
- [ ] 所有 vtable 函数都有实现
- [ ] 地址转换公式与 discover chain Step 5 的记录一致
- [ ] 没有硬编码的魔数——全部通过 config 传入
- [ ] 字节序交换覆盖了 1/2/3/4/8 字节的情况
- [ ] `dsc_arch_register_builtins()` 注册了所有 keep 的 backend
- [ ] 每个函数不超过 50 行
- [ ] Inventory 中 `remove` 的 backend 没有代码
- [ ] 地址转换处理了边界值（0x0, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF）

## Edge Cases
- 如果现有代码有多种地址空间（程序/数据/外设），当前只处理数据空间
- 如果字大小不是 8 的整数倍（罕见），标记 `[NEEDS_HUMAN_REVIEW]`
- 如果 discover chain 没有记录地址转换公式，标记为 `[NEEDS_HUMAN_REVIEW]`
- 如果现有代码同时支持多个架构的动态切换，保持简单——每个 session 一个固定架构

## When Unsure
- **不确定地址转换公式？** 查 discover chain Step 5。如果没有记录，标记 `[NEEDS_HUMAN_REVIEW]`
- **不确定字节序？** 默认 little-endian，并在注释中标注
- **不确定 word_bits？** 查现有代码中的内存访问模式——单次读取的字节数就是字大小
- **完全看不懂地址转换逻辑？** 将整段逻辑作为注释粘贴到代码中，标记 `[NEEDS_HUMAN_REVIEW]`
