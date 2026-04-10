# Step 1: 创建项目骨架

## Role
你是一个 C 项目构建专家，擅长从模板项目创建目录结构和构建系统。

## Task
参考 dsp-connect demo 的 `src/` 目录结构，创建一个空的项目骨架。
只创建目录和头文件，**不写任何实现代码**。

## Context
dsp-connect demo 采用分层架构，每个子目录是一个独立模块。
你的任务是复制这个目录结构，并把 demo 的头文件作为起点。
后续步骤会逐一填充实现。

## Refer to Demo
仔细阅读以下目录和文件：
- `src/` — 整体目录结构
- `src/core/dsc.h` — 顶层 API 定义
- `src/transport/transport.h` — vtable 模式示例
- `src/arch/arch.h` — vtable 模式示例
- `src/dwarf/dwarf_types.h` — 类型系统定义
- `src/util/dsc_common.h` — 通用宏和错误码

## Check Inventory
打开 Inventory JSON，确认以下内容：
- 哪些模块标记为 `keep`（必须创建目录）
- 哪些模块标记为 `remove`（不创建目录）
- 哪些模块标记为 `uncertain`（创建目录但在 README 中标注待确认）

## Rules
1. DO: 严格复制 demo 的目录布局——不增加、不减少、不重命名
2. DO: 复制 demo 的所有 `.h` 文件作为起点
3. DO: 为每个 `.h` 文件创建一个对应的空 `.c` 文件（只有 `#include` 和空函数桩）
4. DON'T: 不要写任何实际实现逻辑——后续步骤会做
5. DON'T: 不要修改头文件中的类型定义和函数签名
6. DON'T: 不要添加 demo 中没有的文件或目录
7. ALWAYS: 每个 `.c` 文件顶部添加 PURPOSE / PATTERN / FOR 注释

## Steps

1. **创建顶层目录**
   ```
   mkdir -p my_softprobe/src/{arch,core,dwarf,format,memory,resolve,transport,util}
   mkdir -p my_softprobe/tests
   ```

2. **复制头文件**
   从 demo 的 `src/` 复制所有 `.h` 文件到对应目录。
   保持文件名和路径完全一致。

3. **调整头文件中的项目特定内容**
   只改这些：
   - 如果 Inventory 中某个 transport 标记为 `remove`，删除对应的头文件
   - 如果 Inventory 中某个 arch backend 标记为 `remove`，删除对应的头文件
   - 保持所有接口头文件（`transport.h`, `arch.h` 等）不变

4. **创建空实现文件**
   为每个 `.h` 创建对应的 `.c`，内容格式：
   ```c
   /* PURPOSE: [从 demo 对应文件复制]
    * PATTERN: [从 demo 对应文件复制]
    * FOR: [从 demo 对应文件复制] */

   #include "对应头文件.h"

   /* TODO: implementation in Step N */
   ```

5. **创建 Makefile**
   参考 demo 的 Makefile，创建基本的构建文件。
   确保 `make` 可以编译（即使所有函数都是空桩）。

6. **验证编译**
   运行 `make` 确保骨架项目可以零警告编译。

## Output Format

```
my_softprobe/
├── Makefile
├── src/
│   ├── arch/
│   │   ├── arch.h              # [copied from demo]
│   │   ├── arch_factory.h      # [copied from demo]
│   │   ├── arch_factory.c      # [stub]
│   │   ├── arch_xxx.h          # [only if keep in inventory]
│   │   └── arch_xxx.c          # [stub]
│   ├── core/
│   │   ├── dsc.h               # [copied from demo]
│   │   ├── dsc.c               # [stub]
│   │   ├── dsc_errors.h        # [copied from demo]
│   │   └── dsc_errors.c        # [stub]
│   ├── dwarf/
│   │   └── ...                 # [same pattern]
│   ├── format/
│   │   └── ...
│   ├── memory/
│   │   └── ...
│   ├── resolve/
│   │   └── ...
│   ├── transport/
│   │   └── ...
│   └── util/
│       └── ...
└── tests/
```

对于 Inventory 中 `uncertain` 的模块，在输出末尾附加：

```markdown
## [NEEDS_HUMAN_REVIEW]
以下目录/文件已创建但状态不确定，需人类确认：
- src/xxx/ — 原因：Inventory 标记为 uncertain，[具体说明]
```

## Quality Checklist
- [ ] 目录结构与 demo 的 `src/` 完全一致（不多不少）
- [ ] 所有 `.h` 文件从 demo 原样复制
- [ ] 所有 `.c` 文件有正确的 `#include` 和 PURPOSE 注释
- [ ] Inventory 中 `remove` 的模块没有对应文件
- [ ] Inventory 中 `uncertain` 的模块有 `[NEEDS_HUMAN_REVIEW]` 标记
- [ ] `make` 可以成功编译（即使函数体是空的）
- [ ] 没有添加 demo 中不存在的文件

## Edge Cases
- 如果 demo 有某个模块但 Inventory 没有提到（如 `util/`），照常创建——这是基础设施
- 如果 Inventory 中有功能但 demo 中没有对应模块，标记为 `[NEEDS_HUMAN_REVIEW]`
- 如果不确定某个头文件是否需要修改，保持原样不动

## When Unsure
如果对任何决策不确定，采用以下策略：
- **不确定是否需要某个文件？** 创建它（多一个空文件不会造成损害）
- **不确定头文件是否需要修改？** 不修改，保持 demo 原样
- **不确定 Makefile 怎么写？** 用最简单的 `gcc -c` 方式，不加优化
- 将所有不确定的决策记录在输出末尾的 `[NEEDS_HUMAN_REVIEW]` 部分
