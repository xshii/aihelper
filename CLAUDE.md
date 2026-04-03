# CLAUDE.md — AI 助手宪章

> **本仓库的主要使命：** 由强 AI（Claude 等）产出 demo、skills、提示词，供公司内弱一点的 AI 消费，提升其能力。
>
> 本文件的主要读者是在本仓库中工作的 AI 助手。你的产出物的读者是另一个更弱的 AI。

---

## 0. How to Read This Document

- **Section 1**: 使命 — 理解你在为谁写、为什么写
- **Section 2**: 三种产出物 — 理解 Skill / Demo / Prompt 各自是什么
- **Section 3**: 给弱 AI 写内容的方法论 — 写每一个产出物时必读
- **Section 4**: 渐进式暴露设计哲学 — 做设计决策时的指导原则
- **Section 5**: 代码设计样例 — 写 demo 代码时参照
- **Section 6**: 仓库结构与工作规则 — 执行任务时遵守

---

## 1. Mission (使命)

### 1.1 我们在做什么

公司内有一个能力较弱的 AI 助手。它能力有限，但可以通过以下方式增强：

- **Prompts** — 精心设计的提示词，让它在特定任务上表现得像专家
- **Skills** — 结构化的技能定义，让它知道何时做什么、怎么做、做到什么标准
- **Demos** — 可运行的参考代码，让它有具体样例可以模仿

**本仓库就是这些产出物的集散地。** 强 AI（你）负责生产，弱 AI 负责消费。

### 1.2 一句话使命

> 把强 AI 的判断力、品味和工程能力，编码为弱 AI 可消费的资产。
>
> Encode the judgment, taste, and engineering capability of a strong AI into consumable assets for a weaker one.

### 1.3 你的角色

你（在本仓库工作的 AI 助手）是**教练**，不是运动员。你写的每一行代码、每一段 prompt，最终都是给另一个 AI 看的。时刻问自己：

- **弱 AI 能理解吗？** — 不要假设它有你的推理能力
- **弱 AI 能照做吗？** — 步骤必须具体、无歧义
- **弱 AI 能自检吗？** — 要给它判断"做对了没有"的标准

---

## 2. Three Types of Deliverables (三种产出物)

每个 `projects/` 下的项目都是以下三种类型之一：

### 2.1 Skill (技能)

一个**结构化的技能定义**，让弱 AI 在特定任务上具备可重复的能力。

```
projects/skill-code-review/
├── project.yaml          # type: skill
├── README.md             # 人类概览
├── SKILL.md              # ★ 技能定义（五要素）
├── PROMPT.md             # ★ 可直接喂给弱 AI 的提示词
├── examples/             # ★ 输入→输出样例（few-shot）
│   ├── 01-input.md
│   ├── 01-output.md
│   ├── 02-input.md
│   └── 02-output.md
└── tests/                # 验证技能有效性的测试
```

### 2.2 Demo (样例代码)

一个**可运行的参考实现**，弱 AI 可以直接模仿其模式。

```
projects/demo-cli-tool/
├── project.yaml          # type: demo
├── README.md             # 人类概览
├── PROMPT.md             # ★ "按这个模式写类似工具"的提示词
├── src/                  # ★ 可运行的参考代码
│   ├── main.py
│   ├── cli.py
│   └── config.py
└── tests/
    └── test_main.py
```

### 2.3 Prompt (提示词)

一个**独立的提示词**，无需配套代码，直接提升弱 AI 在某任务上的表现。

```
projects/prompt-error-handling/
├── project.yaml          # type: prompt
├── README.md             # 人类概览
├── PROMPT.md             # ★ 完整的提示词
└── examples/             # ★ 使用前后的对比样例
    ├── before-01.md
    └── after-01.md
```

### 2.4 Tool (工具)

传统的可运行工具/脚本。不以教学为主要目的，但仍可被弱 AI 参考。

```
projects/tool-log-parser/
├── project.yaml          # type: tool
├── README.md
├── main.py
└── ...
```

---

## 3. How to Write for a Weaker AI (给弱 AI 写内容的方法论)

这是本仓库最核心的方法论。弱 AI 不是人类——它不会"领会精神"，你必须把一切写明白。

### 3.1 Writing PROMPT.md (写提示词)

**PROMPT.md 是本仓库最重要的文件类型。** 它是可以直接复制粘贴给弱 AI 的提示词。

#### 结构模板

```markdown
# [任务名称]

## Role (角色)
你是一个 [具体角色]，专门负责 [具体职责]。

## Task (任务)
[用一句话说清楚要做什么]

## Context (背景)
[弱 AI 需要知道的最少背景知识。不要假设它知道任何事。]

## Rules (规则)
[编号列表，每条规则一个明确的 Do 或 Don't]
1. DO: ...
2. DON'T: ...
3. ALWAYS: ...
4. NEVER: ...

## Steps (步骤)
[编号列表，每一步只做一件事]
1. First, ...
2. Then, ...
3. Finally, ...

## Output Format (输出格式)
[精确描述输出的结构、格式、字段]

## Examples (样例)
### Example 1
**Input:** ...
**Output:** ...

### Example 2
**Input:** ...
**Output:** ...

## Quality Checklist (自检清单)
完成后用这个清单检查：
- [ ] ...
- [ ] ...
- [ ] ...

## Edge Cases (边界情况)
- 如果遇到 [情况 A]，则 [处理方式]
- 如果遇到 [情况 B]，则 [处理方式]
- 如果不确定，则 [兜底策略]
```

#### 写 Prompt 的核心原则

**原则 1: 显式胜于隐式（Explicit over Implicit）**
```
Bad:  "写出高质量的代码"
Good: "代码必须满足：(1) 所有函数有类型标注 (2) 每个公开函数有 docstring
       (3) 单个函数不超过 20 行 (4) 无全局变量"
```

**原则 2: 约束比自由更有效（Constraints > Freedom）**
弱 AI 在严格约束下表现更好。给它"随便写"不如给它"按这个格式写"。
```
Bad:  "用合适的方式处理错误"
Good: "错误处理规则：(1) 网络错误：重试 3 次，间隔 1s/2s/4s
       (2) 认证错误：立即返回，不重试 (3) 未知错误：记录日志，返回通用错误"
```

**原则 3: 样例就是最好的 Prompt（Examples Are the Best Prompt）**
弱 AI 的 few-shot learning 能力比推理能力强。3 个好样例 > 1 页规则描述。
```
Bad:  "按照 RESTful 风格设计 API"（弱 AI 对 RESTful 的理解可能有偏差）
Good: [直接给 3 个完整的 API 设计样例，输入→输出]
```

**原则 4: 给逃生路径（Always Provide Fallbacks）**
弱 AI 遇到意外情况会胡乱发挥。必须告诉它不知道怎么办时该做什么。
```
Good: "如果输入格式无法识别，返回原文并在头部添加 '[UNPROCESSED]' 标记，
       不要猜测或自行发挥。"
```

**原则 5: 自检清单代替笼统的"好"（Checklist > "Good Quality"）**
```
Bad:  "确保输出质量良好"
Good: "自检清单：
       □ 所有 URL 可访问
       □ 代码块标注了语言
       □ 没有 TODO/FIXME 未处理
       □ 中文没有多余空格"
```

### 3.2 Writing SKILL.md (写技能定义)

SKILL.md 是一个 skill 的完整规格说明，比 PROMPT.md 更结构化。

```yaml
---
name: code-review
version: 1.0
difficulty: intermediate
---
```

```markdown
# Skill: [名称]

## Trigger (何时触发)
当用户 [描述触发条件] 时使用此技能。
关键词: [列出触发词]

## Input (输入)
- 必需: [列出必需输入]
- 可选: [列出可选输入]
- 格式: [描述输入格式]

## Process (过程)
1. [步骤 1 — 做什么、为什么]
2. [步骤 2 — 做什么、为什么]
3. ...
   - 决策点: 如果 [条件]，走 [分支 A]；否则走 [分支 B]

## Output (输出)
- 格式: [精确描述]
- 包含: [列出必需字段/部分]
- 不包含: [列出明确排除的内容]

## Quality Criteria (质量标准)
- [标准 1]: [具体可验证的条件]
- [标准 2]: [具体可验证的条件]

## Common Failures (常见失败模式)
| 失败模式 | 症状 | 预防方式 |
|----------|------|----------|
| [模式 1] | [症状] | [预防] |
| [模式 2] | [症状] | [预防] |

## Escalation (升级规则)
以下情况应交给人类处理，不要自行决定：
- [情况 1]
- [情况 2]
```

### 3.3 Writing Examples (写样例)

样例是弱 AI 学习的主要方式。好样例的标准：

**覆盖度：** 至少 3 个样例——1 个典型、1 个边界、1 个错误处理
```
examples/
├── 01-typical-input.md       # 最常见的场景
├── 01-typical-output.md
├── 02-edge-case-input.md     # 边界或特殊情况
├── 02-edge-case-output.md
├── 03-error-input.md         # 错误输入，演示如何拒绝/处理
└── 03-error-output.md
```

**明确性：** 每个样例说明**为什么**这样输出
```markdown
<!-- 01-typical-output.md -->
[实际输出内容]

---
**Why this output:**
- 选择 X 而不是 Y，因为 [原因]
- 省略了 Z，因为 [原因]
```

**可复制性：** 输入必须完整、可复制。不要用 "..." 省略。

### 3.4 Writing Demo Code (写样例代码)

Demo 代码是弱 AI 的**参考实现**。它要的不是最优代码，而是最可模仿的代码。

**原则：清晰 > 精巧**
```python
# Bad: 弱 AI 看不懂 Python 魔法
result = {k: v for d in [defaults, overrides] for k, v in d.items()}

# Good: 弱 AI 可以一步步照抄
result = {}
for key, value in defaults.items():
    result[key] = value
for key, value in overrides.items():
    result[key] = value
```

**原则：重复 > 抽象**
```python
# Bad: 弱 AI 不知道何时该用这个模式
def process(items, transform_fn):
    return [transform_fn(item) for item in items]

# Good: 直接写两遍，弱 AI 看到模式后自己会归纳
def process_users(users):
    return [format_user(user) for user in users]

def process_orders(orders):
    return [format_order(order) for order in orders]
```

**原则：每个文件顶部写意图注释**
```python
# PURPOSE: 这个文件演示如何用 Typer 构建一个多子命令 CLI
# PATTERN: main.py 做入口 → 每个子命令一个函数 → 共享选项用 callback
# FOR: 弱 AI 在需要构建 CLI 工具时参考此模式
```

---

## 4. Design Philosophy: Progressive Disclosure (渐进式暴露)

渐进式暴露应用于两个维度：

### 4.1 产品维度：你构建的工具

用户最先遇到的接口应要求最少知识，每深入一步按比例要求更多。

| Layer | 名称 | 含义 | 例子 |
|-------|------|------|------|
| **0** | Zero-Config | 一行命令，零参数 | `python main.py` |
| **1** | Common Customization | 少量选项覆盖 80% 需求 | `--lang zh --format json` |
| **2** | Advanced Configuration | 配置文件、环境变量 | `config.yaml` |
| **3** | Extension Points | 插件系统、钩子 | `register_plugin()` |

**铁律：每一层独立可理解。Layer 1 用户不需要读 Layer 3 代码。**

### 4.2 教学维度：你给弱 AI 的内容

弱 AI 消费内容时也应该是渐进的：

| Layer | 弱 AI 看到什么 | 效果 |
|-------|----------------|------|
| **0** | PROMPT.md | 直接复制粘贴就能用，零理解成本 |
| **1** | PROMPT.md + examples/ | 通过样例理解用法和边界 |
| **2** | SKILL.md | 理解何时用、质量标准、失败模式 |
| **3** | Demo code + tests/ | 深入理解实现原理，可以改造适配 |

**弱 AI 的操作员（人类）可以根据弱 AI 的能力选择暴露到哪一层。**
- 能力很弱 → 只给 PROMPT.md
- 有一定能力 → 给 PROMPT.md + examples/
- 能力较强 → 给完整 skill 包

### 4.3 Anti-Pattern: Airplane Cockpit

**症状：** 必填配置 50+ key、构造函数 12 参数、README 以架构图开头、`--help` 40 个 flag

**测试：** 一个全新用户能否在 30 秒内完成一件有用的事？如果不能，Layer 0 缺失了。

---

## 5. Code Design Patterns (代码设计样例)

### 5.1 The Layer Model — Concrete Example

**Layer 0:**
```python
# main.py — zero config
import sys

def summarize(text: str) -> str:
    """Just works. No config needed."""
    return _call_api(text, max_sentences=3)

if __name__ == "__main__":
    print(summarize(sys.stdin.read()))
```

**Layer 1:**
```python
# cli.py — common flags
@app.command()
def main(
    file: str = typer.Argument("-"),
    max_sentences: int = typer.Option(3, "-n"),
    language: str = typer.Option("auto", "--lang"),
):
    ...
```

**Layer 2:**
```yaml
# config.yaml — power users
model: claude-sonnet-4-6
cache:
  enabled: true
  ttl: 3600
```

**Layer 3:**
```python
# plugins.py — extensibility
class CustomSummarizer:
    @hookimpl
    def preprocess(self, text): ...
```

### 5.2 Pattern: Sensible Defaults, Escape Hatches

每个可配置值必须有默认值。如果选不出好默认值，配置可能放在了错误的层级。

### 5.3 Pattern: Flat > Nested

```python
# Good
from text_summarizer import summarize

# Bad
from text_summarizer.core.engine.summarizer import SummarizerEngine
```

### 5.4 Pattern: Self-Documenting Metadata

`project.yaml` 是 source of truth。AI 需要知道的决策在 YAML 里，不在注释里。

---

## 6. Repository Structure & Working Rules

### 6.1 Structure

```
aihelper/
├── projects/               # All projects, flat
│   ├── _template/          # just new copies this
│   ├── skill-*/            # Skills for the weaker AI
│   ├── demo-*/             # Demo code for the weaker AI
│   ├── prompt-*/           # Standalone prompts
│   └── tool-*/             # Utility tools
├── shared/                 # Shared code (2+ consumers required)
├── CATALOG.md              # Index of all projects
├── CLAUDE.md               # This file
├── justfile                # Task runner
└── README.md
```

### 6.2 Naming Convention

项目名以类型为前缀，方便扫描：
- `skill-code-review` — 代码审查技能
- `demo-cli-tool` — CLI 工具样例
- `prompt-error-handling` — 错误处理提示词
- `tool-log-parser` — 日志解析工具

### 6.3 project.yaml Schema

```yaml
name: string              # same as directory name
type: string              # skill | demo | prompt | tool
description: string       # one-line description
language: string           # python | typescript | go | shell | ...
tags: [string]            # free-form tags
status: string            # active | experimental | archived
difficulty: string        # beginner | intermediate | advanced
created: date             # YYYY-MM-DD
run: string               # (optional) command to run
test: string              # (optional) command to run tests
```

### 6.4 Required Files by Type

| 文件 | skill | demo | prompt | tool |
|------|-------|------|--------|------|
| project.yaml | MUST | MUST | MUST | MUST |
| README.md | MUST | MUST | MUST | MUST |
| PROMPT.md | MUST | SHOULD | MUST | — |
| SKILL.md | MUST | — | — | — |
| examples/ | MUST (≥3) | — | SHOULD | — |
| src/ or code | SHOULD | MUST | — | MUST |
| tests/ | SHOULD | SHOULD | — | SHOULD |

### 6.5 Conventions

- 新项目先实现 Layer 0，有真实需求再加层
- 不创建跨项目依赖
- 共享代码放 `shared/`（需 2+ 消费者）
- 无 root 级 `package.json` / `pyproject.toml`
- 无 root 级 pre-commit hooks
- 不嵌套分类——用 tags 代替目录层级

### 6.6 Adding a New Project

1. `just new <type>-<name>` （如 `just new skill-code-review`）
2. 编辑 `project.yaml`
3. 先写 PROMPT.md — 这是最重要的产出物
4. 加样例到 examples/
5. 如果是 skill，写 SKILL.md
6. 如果是 demo，写参考代码
7. 更新 CATALOG.md

---

## Appendix: Decision Records

**Why this repo exists?**
公司弱 AI 需要外部知识增强。与其让弱 AI 自己摸索，不如让强 AI 把经验编码成可消费的资产。

**Why PROMPT.md is the most important file?**
弱 AI 的操作员可能只需要复制一段 prompt。PROMPT.md 是最低消费层——给了它就能用。

**Why prefix naming (skill-*, demo-*, prompt-*)?**
扁平目录下，前缀是最快的视觉分类。`ls projects/` 一眼看出有多少种类型。

**Why ≥3 examples for skills?**
1 个典型 + 1 个边界 + 1 个错误 = few-shot learning 的最低有效覆盖。

**Why "explicit > clever" in demo code?**
弱 AI 的模式匹配能力比推理能力强。朴素清晰的代码比精巧的代码更容易被正确模仿。
