# skill-cpp-pybind-facade

> 将丑陋的 C++ 平铺 API（类型爆炸）包装为 Pythonic facade，前端 torch.Tensor。

## 这是什么

一条**8 步 prompt 流水线**，引导弱 AI 逐步完成 C++ → Python binding 封装。

每一步是一个独立的 prompt，弱 AI 只需要理解当前步。步与步之间通过具体的文件交接。

## 流水线概览

```
header.h ──[Step 1]──→ function_table.json
                         │
                   ┌─────┼─────┐
                   ▼     ▼     ▼
              [Step 2] [Step 3] (可并行)
                   │     │
          bindings.cpp  registry.py
                   │     │
                   │  [Step 4]──→ facade.py
                   │     │
                   │  [Step 5]──→ preprocessor.py
                   │     │
                   │  [Step 6]──→ api.py (torch frontend)
                   │     │
                   └─────┤
                   [Step 7]──→ build system
                         │
                   [Step 8]──→ tests
```

## 操作手册（给人类操作员）

### 准备材料
- [ ] C++ 头文件 (`.h`)
- [ ] 编译好的 `.so` 文件
- [ ] 已知的类型列表和专业名词表（可选，帮助 AI 理解术语）

### 操作步骤

| Step | Prompt 文件 | 给 AI 的输入 | AI 产出 | 人类检查点 |
|------|-------------|-------------|---------|-----------|
| 1 | `prompts/01-parse-header.md` | 头文件内容 | `function_table.json` | 检查函数是否都被正确解析 |
| 2 | `prompts/02-gen-bindings.md` | function_table.json | `_raw_bindings.cpp` | 检查生成的 pybind11 代码能否编译 |
| 3 | `prompts/03-build-registry.md` | function_table.json | `registry.py` | 检查注册表是否完整覆盖 |
| 4 | `prompts/04-write-facade.md` | registry.py | `facade.py` | 试调用几个函数看是否正确 dispatch |
| 5 | `prompts/05-add-preprocessor.md` | facade.py | `preprocessor.py` | 检查 hook 是否可插拔 |
| 6 | `prompts/06-torch-frontend.md` | facade.py + preprocessor.py | `api.py` | 用真实 tensor 调用测试 |
| 7 | `prompts/07-build-system.md` | 所有文件 | setup.py / CMakeLists.txt | 试编译 |
| 8 | `prompts/08-test-verify.md` | 所有文件 | tests/ | 跑测试 |

### 关键决策点（人类做，不让 AI 做）

1. **Step 1 之前**：确认头文件中的专业名词和类型命名惯例，写入术语表
2. **Step 3 之后**：确认输出类型推断规则（哪两个类型做运算，结果是什么类型）
3. **Step 5 之后**：确认哪些类型需要外部预处理，预处理接口长什么样
4. **Step 7 之前**：确认编译环境（torch 版本、CUDA 版本、.so 路径）

### 出错回退

- 某步输出有误 → 只重做那一步，不影响其他步
- 弱 AI 理解错了术语 → 在 Step 1 输入中补充术语表，重做 Step 1
- 生成的代码编译失败 → 重做 Step 2，把错误信息一起喂给 AI

## 文件说明

| 文件 | 用途 |
|------|------|
| `DESIGN.md` | 完整架构设计（给人看，不给弱 AI） |
| `prompts/01-08` | 8 个独立的 AI prompt |
| `examples/sample_header.h` | 模拟的丑陋头文件 |
| `examples/function_table.json` | Step 1 的期望输出 |
| `examples/*.py` | 各步骤的期望输出代码 |
