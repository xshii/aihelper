# Rewrite Chain — 用 dsp-connect 架构重写现有 C++ 软调代码

## 目标

将现有 C++ softprobe 代码重写为 C 代码，严格使用 dsp-connect demo 作为架构模板。
产出一个与 dsp-connect 结构对齐的全新 C 代码库。

## 前置条件

1. **已完成 discover 链**，手头有 Inventory JSON 文件（来自 discover/07-inventory-report.md）
2. **可访问 dsp-connect demo 源码**（`src/` 目录）
3. **可访问现有 C++ 软调代码库**（需要读取实现细节）
4. 理解 Inventory 中的三种状态：`keep` / `remove` / `uncertain`

## 核心原则

**不是重写所有代码。** 只重写 Inventory 中标记为 `keep` 的功能。

| Inventory 状态 | 你的行动 |
|----------------|----------|
| `keep` | 参考 demo 架构，重写为 C 代码 |
| `remove` | **跳过，不写任何代码** |
| `uncertain` | **不写代码**，在输出中标记 `[NEEDS_HUMAN_REVIEW]`，说明原因 |

## 链结构

| 步骤 | 文件 | 做什么 | 依赖 |
|------|------|--------|------|
| 1 | 01-scaffold-project.md | 创建目录骨架 | 无 |
| 2 | 02-implement-dwarf-layer.md | DWARF 解析层 | Step 1 |
| 3 | 03-implement-transport.md | 通信传输层 | Step 1 |
| 4 | 04-implement-arch.md | 架构适配层 | Step 1 |
| 5 | 05-implement-resolve.md | 符号解析层 | Step 2 |
| 6 | 06-implement-memory.md | 内存读写层 | Step 3, 4 |
| 7 | 07-implement-format.md | 格式化层 | Step 2 |
| 8 | 08-implement-core.md | 核心集成层 | Step 2-7 |
| 9 | 09-integration-test.md | 集成测试 | Step 8 |

## 预期产出

```
my_softprobe/
├── src/
│   ├── arch/          # 架构适配（地址转换、字节序）
│   ├── core/          # 顶层 API（open/close/read_var）
│   ├── dwarf/         # DWARF 解析（符号、类型）
│   ├── format/        # 类型格式化（struct/enum/array/基本类型）
│   ├── memory/        # 内存读写（地址翻译 + 传输）
│   ├── resolve/       # 路径解析（"g_config.mode" → 地址+类型）
│   ├── transport/     # 通信层（telnet/serial/...）
│   └── util/          # 工具函数（hashmap/log/strbuf）
├── tests/
│   └── ...            # 集成测试
└── Makefile
```

## 迭代模型

每一步允许失败和重试。如果某一步的实现不正确：
1. 不要推倒重来——只修改有问题的部分
2. 向前步骤的输出是后续步骤的输入——修改后检查下游是否受影响
3. 如果遇到 Inventory 中没有覆盖的功能，标记为 `[NEEDS_HUMAN_REVIEW]`

## 注意事项

- 每个 .c 文件顶部必须有 PURPOSE / PATTERN / FOR 注释（和 demo 一样）
- 每个函数不超过 50 行——超过必须拆分为 helper
- 优先保证正确性，其次是完整性，最后是性能
- 不要"发明"demo 中没有的抽象——严格照搬 demo 的架构模式
