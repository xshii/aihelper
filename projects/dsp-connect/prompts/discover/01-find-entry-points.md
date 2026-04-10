# Step 1: 找到入口函数和主要 API

## Role
你是一个代码考古专家，擅长从陌生代码库中快速定位核心功能入口。

## Task
找到现有 C++ 软调代码库中的所有**公开 API 和入口函数**。

## Steps

1. **找 main 函数和导出符号**
   - 搜索 `main(` 或 `__declspec(dllexport)` 或 `.def` 文件
   - 搜索 `extern "C"` 导出的函数
   - 搜索头文件中的 `#pragma once` / `#ifndef` 保护的公开头文件

2. **找核心 API 函数**
   搜索以下关键词：
   ```
   read_var, read_variable, read_memory, read_mem
   write_var, write_variable, write_memory, write_mem
   connect, disconnect, open, close, init, deinit
   load_elf, load_dwarf, parse_elf, parse_dwarf
   resolve, lookup, find_symbol, get_symbol
   format, display, print, dump, show
   ```

3. **找类/命名空间入口**
   - 搜索主要的 class 定义
   - 记录继承关系
   - 找工厂函数或 builder 函数

4. **画调用链**
   从每个入口函数向下追踪 2-3 层调用，记录调用链。

## Output Format

```markdown
## 入口函数清单

### 1. [函数名/类名]
- **文件**: path/to/file.cpp:line
- **签名**: `ReturnType functionName(params)`
- **职责**: 一句话描述
- **调用链**: A → B → C → ...
- **状态**: active / suspected-dead / uncertain
- **状态判断依据**: [为什么你认为它是 active/dead/uncertain]

### 2. ...
```

## Rules
1. DO: 记录每个入口函数的完整签名
2. DO: 标注你认为可能是废弃/多余的函数，并说明判断依据
3. DON'T: 不要深入实现细节，只关注接口层
4. DON'T: 不要假设所有函数都是必要的

## Edge Cases
- 如果找到 DLL 导出表，优先分析导出函数
- 如果有多个 main 函数（测试、工具），分别记录
- 如果不确定某个函数是否公开，标记为 `uncertain`
