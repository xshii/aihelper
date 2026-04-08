# Harness Engineering 方法论

> 本文档定义 dsp-core 的验证治理框架。适用于强 AI 维护、弱 AI 消费的场景。

---

## 核心问题

> **你怎么知道 prompt 对弱 AI 有效？**

传统 CI 回答的是"代码能跑"。Harness engineering 回答的是"弱 AI 按 prompt 操作后，产出是正确的"。

---

## 分层模型

| 层级 | 名称 | 回答的问题 | 实现方式 | 状态 |
|------|------|-----------|---------|------|
| L0 | CI 基础 | 代码能跑吗？ | `make ci` (lint + quality + test) | 已实现 |
| L1 | Prompt 完整性 | prompt 引用的文件还在吗？ | `check_prompt_refs.py` | 已实现 |
| L2 | Eval-Driven | 弱 AI 的产出结构正确吗？ | `prompts/eval/eval_*.py` | 已实现 |
| L3 | 结构校验 | 已有代码符合规范吗？ | `check_structure.py` | 已实现 |
| L4 | E2E Smoke | 全流程跑得通吗？ | `scripts/smoke_test.py` | 已实现 |
| L5 | Math 验证 | 算法数学上正确吗？ | `math_strategy` + expected 比对 | 已实现 |
| L6 | Prompt Regression | 代码改后 prompt 还有效吗？ | 需接弱 AI API | 未实现 |
| L7 | LLM-as-Judge | 强 AI 评估弱 AI 产出质量 | 需接强 AI API | 未实现 |

**L0-L5 已实现，L6-L7 需要模型 API，待基础设施就绪后补充。**

---

## L0: CI 基础

```
make ci = lint → quality → test → smoke
```

| 检查项 | 工具 | 阈值 |
|--------|------|------|
| 语法错误 + 风格 | ruff | E/W/F（忽略 E501, F401, E402） |
| 架构分层 | import-linter | core→golden→data→ops→context |
| 圈复杂度 | radon CC | < C (10) |
| 可维护性 | radon MI | > B (20) |
| 死代码 | vulture | confidence ≥ 80% |
| 函数长度 | check_func_length.py | 非空非注释 ≤ 50 行 |
| 单元/集成测试 | pytest | 全 pass |
| E2E 全流程 | smoke_test.py | 8 策略 + 比数无 FAIL |

---

## L1: Prompt 完整性

**工具：** `scripts/check_prompt_refs.py`

扫描 `prompts/*.md` 和 `PROMPT.md`，提取所有 backtick 内的文件路径引用（`src/...`、`tests/...`），检查文件是否存在。

**触发时机：** `make lint` 自动执行。

**为什么需要：** 代码重构（重命名文件/函数）后，prompt 中的引用会漂移。弱 AI 按过时的 prompt 操作会找不到文件。

---

## L2: Eval-Driven

**工具：** `prompts/eval/eval_*.py`

每个 prompt 对应一个 eval 脚本，定义弱 AI 产出的**结构性验收标准**。

### 设计原则

1. **先写 eval 再写 prompt** — eval 定义"正确长什么样"，prompt 指导如何达到
2. **eval 是可执行的** — 一行命令，PASS 或 FAIL
3. **eval 检查结构不检查语义** — 有 @register_op ≠ 实现正确，但没有 @register_op 一定不正确

### 使用流程

```
操作员给弱 AI → prompt 02 + 算子需求
弱 AI 产出代码
操作员运行 → .venv/bin/python prompts/eval/eval_02_op.py beamform
  [PASS] ops/beamform.py 存在
  [PASS] 有 @register_op
  [PASS] __init__.py 有 import
  [FAIL] __init__.py 有便捷函数     ← 弱 AI 忘了
  EVAL FAILED
操作员反馈给弱 AI → "缺少便捷函数"
```

### 当前 eval 覆盖

| Eval | 对应 Prompt | 参数 | 检查项 |
|------|------------|------|--------|
| eval_01_codec.py | 01-add-codec | dtype_name | Codec 类 + 继承 + 运行时注册 |
| eval_02_op.py | 02-add-op | op_name | 文件 + 装饰器 + import + 便捷函数 + 调用 + 测试 |
| eval_03_golden.py | 03-bridge-golden-c | op_name | COMPUTE 表条目 + 字段类型 |
| eval_05_dtype.py | 05-add-dtype | dtype_name | 定义 + 枚举 + 导出 + 运行时访问 |
| eval_06_convention.py | 06-add-op-convention | op_name | 类定义 + 运行时注册 + 方法存在 |

prompt 04（写测试）的 eval 就是 `make test-ut`——测试的验收标准是测试本身通过。

---

## L3: 结构校验

**工具：** `scripts/check_structure.py`

扫描 `ops/` 下所有算子文件，验证每个算子：
1. 有 `@register_op` 装饰器
2. `ops/__init__.py` 有 import
3. `ops/__init__.py` 有便捷函数
4. `tests/` 下有相关测试
5. 函数参数有类型标注

**和 L2 的区别：** L2 检查"新加的东西对不对"（增量），L3 检查"所有已有的东西是否合规"（全量）。L3 在 `make lint` 中自动执行。

---

## L5: Math 验证

**工具：** `@register_op(math_strategy=fn)` + `save_op_expected` + `report.py`

### 闭环流程

```
generate_input (math 轮):
  math_strategy 替换 randn 输入 → 计算 expected output → 存盘
  
use_input (math 目录):
  加载相同输入 → torch/pq/gc 三种模式分别计算
  
比数:
  1. torch vs pq vs gc（模式间比较）
  2. torch vs expected（数学正确性验证）← math strategy 的核心价值
```

### 设计约束

- math_strategy 返回 `(replacements_dict, expected_tensor)`
- expected 存为 `*_expected0_*.txt`，和 output 文件同目录
- 比数时自动对比 expected vs 各模式 actual
- 没有 math_strategy 的 op 自动降级为随机数据
- near-diagonal target 用固定 seed RNG，保证链条中一致

---

## 扩展点（L6-L7）

### L6: Prompt Regression（需要弱 AI API）

当代码变更时，自动重跑 prompt 链：
1. 给弱 AI 输入 prompt + 需求
2. 弱 AI 产出代码
3. 跑 eval 脚本验证
4. 对比和上次的差异

**前置条件：** 弱 AI 的 API 接口 + eval 脚本（L2 已具备）。

### L7: LLM-as-Judge（需要强 AI API）

用强 AI 评估弱 AI 产出的代码质量：
- 不只检查结构（L2/L3 已覆盖），还检查语义
- 如：实现逻辑是否和数学公式一致、边界处理是否合理

**前置条件：** 强 AI API + 评估 prompt（待设计）。

---

## 文件清单

```
scripts/
├── check_func_length.py   # L0: 函数长度 ≤ 50
├── check_prompt_refs.py   # L1: prompt 路径引用
├── check_structure.py     # L3: 算子结构合规
└── smoke_test.py          # L4: E2E 全流程

prompts/eval/
├── README.md              # 使用说明
├── eval_01_codec.py       # L2: 添加 codec
├── eval_02_op.py          # L2: 添加算子
├── eval_03_golden.py      # L2: 注册 golden C
├── eval_05_dtype.py       # L2: 添加 dtype
└── eval_06_convention.py  # L2: 添加 convention
```
