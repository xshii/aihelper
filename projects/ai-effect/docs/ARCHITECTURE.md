# 算子调试与对照工具 — 架构设计

> 本文已纳入评审修订(2026-05-26)。三项承重决策见
> [adr/0001-paired-per-op-and-v0-scope.md](adr/0001-paired-per-op-and-v0-scope.md)。
> 与初稿的主要差异在 §3 用方框标出。

## 1. 概述

一个 **基于 Clang AST 的源到源代码工具 + 运行时 hook 库 + 离线对比分析器** 的组合系统。

- **编译期(L1)**:libclang 解析源码,识别算子调用和硬件宏,**自动插入 hook 调用**(源码不变,生成新的 `.c`)
- **链接期**:hook 调用绑定到 **运行时 hook 库(L2)**
- **运行期(L2)**:hook 库做 trace dump(把片上数据 DMA 搬到 host)
- **离线(L3)**:Python 分析器读 trace,**把每个算子的硬件真实输入喂给 host reference**,逐算子对比,产出报告

## 2. 设计原则

| 原则 | 含义 | 体现 |
|------|------|------|
| 单向依赖 | 上层依赖下层,反之不行 | 严格 4 层 |
| 关注点分离 | 插桩(位置)、Hook(搬运)、对比(分析+reference)各管各的 | L1/L2/L3 分离 |
| 声明式优先 | 规则用声明式表达 | Pattern DSL 用 Python 装饰器 + 宏参数语义描述符 |
| 主流技术栈 | Clang AST + Python | 不用 Coccinelle/OCaml 等小众工具 |
| 上游红利 | 借力成熟工具 | Clang 前端、NumPy 直接用 |
| KISS | 不需要的复杂度先不引入 | CFG / Plugin / Web / SKIP 类模式都不进 V0 |

## 3. 评审修订(相对初稿的三处承重变更)

> **决策 A —— 对比模型改为 paired per-op(逐算子配对),reference 归 L3 离线。**
> 初稿设计为"跑硬件出一份 trace + 独立跑 reference 出另一份 trace,按 op_id 对齐"。
> 问题:reference 若端到端独立跑,其每个算子的输入是 ref 自算的,一旦前面分叉,
> 后面全错,无法判断"输入一致但输出错"(FR-4.4 做不干净)。
> **改为**:硬件跑一遍 `DUMP_AND_RUN`,dump 每个算子的**输入 + 输出**;离线把每个算子的
> **硬件真实输入**喂给 reference,比 `ref(硬件输入)` 与 `硬件输出`。每个算子独立成案。
> **后果**:V0 核心路径**不需要在设备上跑 reference**,reference 全部用 NumPy 写在 **L3**。

> **决策 B —— V0 只做 `DUMP_AND_RUN`,SKIP 类模式推到 V1。**
> `REPLACE_WITH_REF` / `DUMP_AND_SKIP` 需要"把原宏调用包进 `if` 跳过",这是语句改写,
> 初稿的纯插入 Edit 模型表达不了;且需要 host→device 写回路径。配合决策 A,V0 对比根本
> 不需要它们。它们退化成 **bisection 专用(UC-2)**,V1 再做。

> **决策 C —— 承认"免适配"的边界:每种宏配一份声明式参数语义描述符。**
> 硬件宏多为"裸地址 + 寄存器值",C 类型系统里 `float*` 不携带长度。要 dump 出有意义的
> tensor(shape/dtype/字节数),每种宏仍需一份**声明式描述**:哪个参数是指针、哪个是它的
> 元素数/shape、dtype 是什么。零适配能自动**插 hook**;但**dump 出语义**需要这份描述符。

## 4. 业界参考与定位

- **hipify-clang(AMD)**:借鉴 Clang 前端解析 + AST matcher 模式识别。本工具用 libclang Python 绑定(更轻量,Python 生态友好)。
- **onnx-mlir(InstrumentONNXPass + RunONNXModel.py)**:借鉴三层解耦、选择器设计(`--instrument-ops` 通配符+列表)、Action 可组合。本工具沿用三层 + 同样的选择器。
- **Coccinelle**:借鉴"不展开宏的 parser 思路"、声明式 Pattern + Isomorphism、source-level patch。本工具在 Clang AST 上**复刻**这些机制(Coccinelle 用 OCaml + 小众,LLM 不熟)。**不借鉴** CTL Model Checker、自定义 C parser、SmPL 语言本身。

## 5. 总体架构

### 5.1 层级图

```
┌──────────────────────────────────────────────────┐
│  L4  Orchestrator    (CLI / Pipeline)             │
│      pa-debug instrument / build / run / diff      │
├──────────────────────────────────────────────────┤
│  L3  Offline Analyzer    (Python, 纯离线)          │
│      TraceReader / Differ / DivergenceLocator      │
│      Reference(NumPy) / Reporter                   │  ← reference 在这里(决策 A)
├──────────────────────────────────────────────────┤
│  L2  Runtime Hook Library    (C/C++, 被链接)       │
│      HookDispatcher / DmaExporter / TraceWriter    │  ← V0 只 dump(决策 B)
├──────────────────────────────────────────────────┤
│  L1  Compile-time Transformer    (Python)          │
│      Pattern Engine + Rule Library                 │
│      Hook Inserter(只插函数调用)                  │
└──────────────────────────────────────────────────┘

依赖方向:L4 → L3 → L2(运行时产物=trace 文件) / L1(编译时)
```

### 5.2 依赖规则

- L4 调 L3 和 L1
- L3 读 L2 产出的 trace 文件(只读);L3 内含 reference
- L2 是被插桩代码链接;L1 不直接依赖 L2
- **L1 ↔ L2 唯一耦合点是 hook 函数 ABI**(一份 hook 签名定义)

## 6. 各层详细设计

### 6.1 L1 Compile-time Transformer

**职责**:解析源码 → 识别算子/宏调用 → 在源码层插入 hook 调用 → 输出新的 `.c` 文件 + op_id 站点清单。

```
Rule Library         用户/AI 写的规则集合(每种宏一份描述符)
Pattern Engine       Matcher(AST/Token 谓词) / Capture(变量+参数语义) / Iso(等价归一) / Transformer(基于 location 改写)
IR Layer             复用 Clang:AST(Cursor) / Tokens / Preproc(PreprocessingRecord)
Frontend             libclang 薄封装
```

#### 6.1.1 宏的保留(关键技术点)

Clang 默认展开宏、丢失宏身份。本工具:

- 解析时开启 `TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD`
- 用 `CursorKind.MACRO_INSTANTIATION` 遍历宏展开点(拿到宏名 + 源码 range)
- 用 `clang_tokenize` 拿原始 token

> **⚠ 核心难点(评审 D):libclang 不提供结构化的宏参数。**
> `MACRO_INSTANTIATION` cursor 只给宏名 + range,**不给** `arg(0)` 之类的 API。提取参数必须:
> 对 range 重新 tokenize → 自己写一个**参数分割器**(按逗号切,正确处理嵌套括号、字符串、
> 嵌套调用里的逗号)。这是 PoC 必须先攻克的真正难点,不是"借现成 API"。

#### 6.1.2 stub header

自定义 intrinsics 必须用 stub header 让 Clang 能解析,声明:

- 函数原型(签名匹配真实定义)
- 宏定义(可空展开或简化展开,但**保留参数列表**)
- typedef(`pa_tensor_t` 等关键类型)
- attribute / annotation(`__attribute__((annotate("...")))`,Clang 兼容,自研编译器忽略)

注:annotate 等标注只存在于**分析用的 stub header**,不进入插桩后的 `.c`。插桩后代码里只有
`pa_hook_*(...)` 调用,需配一份自研编译器能接受的 hook 声明头。

#### 6.1.3 宏参数语义描述符(决策 C 落地)+ 配置/框架隔离

每种宏一条规则,声明每个参数的**语义角色**(id/in/out/meta)。规则是一个 `Rule` 实例,
写在**项目的 rules/ 目录**里(不是框架代码),由 `rules_loader` 运行时动态加载:

```python
# rules/hardware_macros/conv.py —— 项目专属配置,不是框架代码
from pa_debug.l1_transformer.rule import Arg, Rule

RULE = Rule(
    macro="PA_INSTR_CONV",
    op="CONV",
    args=[
        Arg("op_id", role="id"),
        Arg("in",  role="in",  dtype="f16", shape_from="ish"),  # dump 据此知道搬哪段、多大
        Arg("w",   role="in",  dtype="f16", shape_from="wsh"),
        Arg("out", role="out", dtype="f16", shape_from="osh"),
        Arg("ish", role="meta"), Arg("wsh", role="meta"), Arg("osh", role="meta"),
    ],
)
```

> 没有 size/shape 信息的宏只能插 hook、不能 dump 有意义 tensor —— 这是"免适配"的明确边界。

**配置/框架隔离(端口与适配器)**:
- **框架(port + 引擎,零项目值)**:`rule.py` 定义 `Rule`/`Arg` *类型*;`rules_loader.py`
  扫描规则目录、动态加载(importlib)模块级 `RULE` / `RULES`,返回 `list[Rule]`。
- **配置(adapter,项目专属)**:`rules/**/*.py` 里的 `Rule` *实例*。新增一种宏 = 丢一个文件,
  **不改框架**(已有 fixture 证明)。
- **组合根**:CLI(`--rules-dir`)读目录 → 加载规则 → 注入 `instrument()`。
- 机器相关的 libclang 路径不写死在框架:bundled 加载失败时由环境变量 `PA_LIBCLANG_PATH` 覆盖。

**规则目录**:

```
rules/
├── hardware_macros/      每种宏一个文件(conv.py ...,定义 RULE = Rule(...))
├── operator_interfaces/  算子接口(softmax.py ...)
├── isomorphisms.py       等价类声明(宏别名归一)
└── blacklist.py          黑名单(文件/函数/非语句位置宏)
```

#### 6.1.4 Transformer(Edit 模型)

- 不修改 AST,基于 source location 做字符串改写
- 每个 `Edit` 是 `(file, offset, length, replacement)`(`length=0` 为纯插入)
- 所有 Edit 按 offset **倒序**应用(避免位置失效)
- 输出新 `.c`(原文件不动)+ op_id 站点清单(JSON)

> **V0 约束(评审 H)**:只处理**语句位置**的宏(独立成句)。出现在表达式里的宏
> (`x = PA_INSTR_CONV(...)`)前后插语句非法,V0 进黑名单,V1 再支持语句包裹。

#### 6.1.5 op_id 的静态/动态拆分(评审 E)

- **静态站点 id**:transformer 生成(如 `file:line:seq`),写进站点清单
- **运行期计数**:同一站点每次调用,hook 库维护 per-site 计数器(即 `iter`)
- **最终 op_id** = `静态站点 id` + 运行期计数,在运行时拼出
- paired per-op 模型下,reference 用的就是该 op 自己 dump 的输入,**无需跨两次 run 对齐**,
  大幅降低数据相关控制流带来的对齐风险

#### 6.1.6 CFG / Isomorphism

- 本期所有规则都是**局部模式匹配**,不需要控制流分析。将来("宏 A 后必有宏 B")再经 C++ binding 暴露 `clang::CFG`,Pattern 预留 `match_path()`。
- Isomorphism:声明宏别名(`PA_CONV → PA_INSTR_CONV`),matcher 比对前先归一,避免规则爆炸。

### 6.2 L2 Runtime Hook Library

**职责**:实现 hook 函数运行时行为。被插桩代码链接它。**V0 只 dump。**

#### 6.2.1 Hook ABI(L1 ↔ L2 唯一契约)

```c
typedef struct {
    const char* op_name;        // "CONV" / "SOFTMAX" / ...
    const char* site_id;        // 静态站点 id(transformer 生成)
    pa_tensor_t** inputs;  int n_inputs;
    pa_tensor_t** outputs; int n_outputs;
    void* attrs;                // 算子专有属性
} pa_hook_ctx_t;

typedef enum {
    PA_ACTION_CONTINUE,         // 继续执行原指令
    PA_ACTION_SKIP,             // 跳过原指令(V1 起用)
} pa_hook_action_t;

pa_hook_action_t pa_hook_before(pa_hook_ctx_t* ctx);
void             pa_hook_after(pa_hook_ctx_t* ctx);
```

#### 6.2.2 Hook 模式

| 模式 | before | 执行原指令 | after | 版本 |
|------|--------|-----------|-------|------|
| `DUMP_AND_RUN` | DMA dump inputs | 是 | DMA dump outputs | **V0** |
| `HASH_ONLY` | 算 inputs hash | 是 | 算 outputs hash | V1 |
| `PASSTHROUGH` | (无) | 是 | (无) | V1 |
| `DUMP_AND_SKIP` | dump inputs + 写回 ref 输出 | 否 | dump outputs | V1 |
| `REPLACE_WITH_REF` | 写回 ref 输出 | 否 | (无) | V1 |

> SKIP 类(后两行)需 host→device 写回(dump 的逆向、同样硬件相关),与 bisection(UC-2)
> 一起在 V1 做。`HASH_ONLY` 仅用于"两次硬件 run 间的廉价回归烟测",**不喂给浮点 Differ**
> (hash 只判 bit-exact,而本工具定位是算法/参数级,非 bit 级 —— 评审 G)。

#### 6.2.3 内部子模块

- `HookDispatcher`:查 site_id → 配置的 mode → 分发 handler;维护 per-site 计数器
- `DmaExporter`:DMA 把片上数据搬到 host(实现依赖硬件 SDK,V0 可用 mock)
- `TraceWriter`:写结构化 trace(JSONL + 关联二进制)
- `Config`:运行时配置(文件 / 环境变量)

#### 6.2.4 Trace 格式(JSONL + 关联文件)

```jsonl
{"op_id":"conv@f.c:42:0#5","op":"CONV","phase":"before","ts":...,"iter":5,
 "inputs":[{"shape":[1,64,56,56],"dtype":"f16","data_ref":"t0001.bin","hash":"abc"}],
 "attrs":{"stride":2,"padding":1}}
{"op_id":"conv@f.c:42:0#5","op":"CONV","phase":"after","ts":...,
 "outputs":[{"shape":[1,128,28,28],"dtype":"f16","data_ref":"t0002.bin","hash":"def"}]}
```

### 6.3 L3 Offline Analyzer

**职责**:读硬件 trace → 逐算子把硬件真实输入喂给 reference → 对比 → 报告。**reference 在此层。**

#### 6.3.1 子模块

- `TraceReader`:读 JSONL + 关联数据,产出 `TraceEvent` 流
- `Reference`:host 侧 NumPy 等价实现,每种宏一个 `ref_<op>(inputs, attrs) -> outputs`
- `Differ`:多种容差比对(abs / rel / cosine / max diff)
- `DivergenceLocator`:扫时序找首个发散点,分类:
  - 类型 A:`ref(硬件输入) ≉ 硬件输出` → **本算子 bug**
  - 类型 B:本算子输入本身已偏离上游理应输出 → **上游传染**,继续向上追
- `Reporter`:JSON 报告 + HTML 报告(Jinja 模板)
- `Visualizer`(V2+):Graphviz / Mermaid 渲染算子图,高亮发散点

> paired per-op 下,A/B 分类靠"逐算子 `ref(本算子真实输入)` vs `本算子真实输出`"得出,
> 不依赖第二条独立 trace。

#### 6.3.2 对比配置(示例)

```yaml
tolerance:
  default: { abs: 1e-3, rel: 1e-3 }
  conv:    { abs: 1e-2, rel: 1e-2 }   # 单算子覆盖
metrics: [abs, rel, cosine, max_diff]
report: { format: [json, html], output: ./reports/ }
```

> **评审 J(方法学风险)**:ref 与硬件天然有舍入/累加顺序差异;首发散判定对 per-op 容差
> **高度敏感**(太紧处处假阳性,太松漏真 bug)。容差标定是真功夫,需结合硬件数值行为
> (如 f16 conv 累加)逐算子校准。文档定位:**算法/参数级别对照,不是 bit 级**。

### 6.4 L4 Orchestrator

CLI 入口,串起 pipeline。

- `pa-debug instrument <src>`:跑 L1,产出插桩后源码 + 站点清单
- `pa-debug build`:编译插桩版本(调自研编译器)
- `pa-debug run`:跑硬件,收集 trace
- `pa-debug diff <hw_trace>`:跑 L3(内部调 reference),产出报告
- `pa-debug full <model>`:一条龙

配置文件 `pa-debug.yaml`:

```yaml
project: my_model
src_dirs: [./src]
stub_headers: [./stubs/pa_intrinsics.h]
rules_dir: ./rules
hook_modes:
  default: DUMP_AND_RUN
tolerance: { abs: 1e-3, rel: 1e-3 }
output_dir: ./out
```

## 7. 关键流程

### 7.1 编译期插桩
```
源码 .c + stub_header.h
  → libclang parse(开 PreprocessingRecord)
  → AST + Tokens + Macro Records
  → Pattern Engine 遍历,每条规则 try match
  → 匹配 → capture(变量 + 参数语义) → 产生 Edit
  → 所有 Edit 按 offset 倒序应用
  → 输出插桩后 .c + op_id 站点清单(JSON)
```

### 7.2 运行期 hook(V0)
```
被插桩代码运行到 pa_hook_before(ctx)
  → HookDispatcher 查 site_id → mode(V0=DUMP_AND_RUN)
  → DmaExporter dump inputs → TraceWriter 写 JSONL → 返回 CONTINUE
被插桩代码执行原指令
  → pa_hook_after(ctx) → dump outputs → 写 JSONL
```

### 7.3 离线对比(paired per-op)
```
硬件 trace(.jsonl + 数据文件)
  → TraceReader 加载 → TraceEvent 流
  → 对每个算子:取其 inputs → Reference.ref_<op>(inputs, attrs) → 理应 outputs
  → Differ 比 理应 outputs vs 硬件 outputs(多种容差)
  → DivergenceLocator 找首发散 + 分 A/B 类
  → Reporter 产出 JSON + HTML
```

## 8. 数据模型(关键接口)

### 8.1 L1(已实现)
```python
@dataclass
class Arg:       name: str; role: str; dtype: str | None; shape_from: str | None  # role: id/in/out/meta
@dataclass
class Rule:      macro: str; op: str; args: list[Arg]      # 含 input_indices/output_indices/id_index
@dataclass
class MacroCall: name: str; args: list[str]; start_offset: int; end_offset: int   # 宏调用的源码区间
@dataclass
class Edit:      offset: int; length: int; replacement: str                       # length=0 → 纯插入
@dataclass
class Site:      site_id: str; op: str; macro: str; file: str; line: int; args: list[str]  # 站点清单条目
```
> `rule.py` 持有 `Rule`/`Arg`(类型/port);`rules_loader.py` 动态加载外置 `rules/` 里的 `Rule` 实例。

### 8.2 Trace Event(L2 产出 / L3 消费)
```python
@dataclass
class TraceEvent:
    op_id: str
    op_name: str
    phase: Literal["before", "after"]
    timestamp: int
    iter: int
    tensors: list[TensorRef]    # shape/dtype/data_ref/hash
    attrs: dict
```

### 8.3 L3 输出
```python
@dataclass
class DiffResult:
    op_id: str
    outputs_diverged: bool
    metrics: dict[str, float]                                  # {"abs":0.3,"rel":0.05,...}
    classification: Literal["clean", "self_bug", "upstream_diverged"]
@dataclass
class Report:
    first_divergence: DiffResult | None
    all_diffs: list[DiffResult]
    summary: dict
```

## 9. 演进路径

### V0 (MVP, 3 个月)
- L1 最小版:1 种宏(`PA_INSTR_CONV`)+ token 级参数提取 + 语义描述符
- L2 最小版:`DUMP_AND_RUN`(DmaExporter 可 mock)+ TraceWriter
- L3:1 个算子的 NumPy reference + abs diff + 首发散定位
- L4:CLI 串起来
- **PoC 目标**:验证 libclang + 宏处理可行(见 §12)

### V1 (6 个月)
- L1 全部 5-6 种宏 + 主要算子接口 + 语句包裹(支持 SKIP)
- L2 全部 hook 模式(含 SKIP 类 + host→device 写回)
- 完整 reference 库 + 多种容差 + A/B 分类 + HTML 报告
- 真实模型端到端;bisection(UC-2)

### V2
- 内存编排分析(L3 新增 Analyzer)+ 依赖图/时序可视化
- 线上 trace 采集 + 离线对照(UC-3)
- Plugin 机制

### V3+
- Web Dashboard / 性能维度 / 规格驱动 reference 自动生成

## 10. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| Clang 无法解析自研宏 | L1 不工作 | stub header 早投入,PoC 优先验证 |
| **宏参数 token 级提取复杂(D)** | L1 开发风险 | PoC 第一周专攻参数分割器;配 fixture |
| 无 shape 信息的宏 dump 不出语义(C) | 免适配边界 | 每种宏配语义描述符;文档写实边界 |
| DMA 导出性能差 | 真硬件可用性 | 支持采样;`HASH_ONLY` 烟测;V0 用 mock |
| Reference 与硬件漂移 | 假阳性 | reference 版本号 + CI 校验 |
| 自研编译器对插桩代码兼容性差 | 编译失败 | 早跑最小用例;插桩代码风格保守 |
| **容差标定难(J)** | 假阳/漏报 | per-op 容差;结合硬件数值行为校准;定位非 bit 级 |
| 规则维护成本随算子上升 | 新算子慢 | 声明式 + fixture + LLM 协助生成 |

## 11. 测试策略

- **L1**:每条规则配 fixture(`input.c` + `expected.c`),CI 跑 diff
- **L2**:hook 模式单元测试;TraceWriter 格式测试
- **L3**:reference 对拍 NumPy 黄金值;trace fixture + 期望报告 JSON
- **L4**:端到端集成(用 mock hook 库 + 模拟 trace),**不依赖真硬件**

## 12. 实施第一步:V0 PoC

**目标**:用 libclang Python 写一个最小可行的 macro pattern engine。

1. 准备一段简单源码(含 `PA_INSTR_CONV(...)` 调用)
2. 写对应 stub header
3. libclang(开 `DetailedPreprocessingRecord`)解析
4. 遍历宏展开点,**token 级提取宏参数**(核心难点 D)
5. 源码层插入 `pa_hook_before` / `pa_hook_after`
6. 输出新 `.c`,目视检查

**预期**:200–300 行 Python。**验证**:(a) Clang 能否借 stub header 解析含自定义宏的源码;
(b) 宏调用位置与参数能否准确提取;(c) 源码改写是否保留原结构。
PoC 通过即证明 L1 可行,再铺开规则与上层模块。

## 13. 目录结构

```
ai-effect/
├── docs/{REQUIREMENTS,ARCHITECTURE}.md, adr/
├── pa_debug/                 # Python 包
│   ├── l1_transformer/{frontend,pattern_engine,rules_runtime}/
│   ├── l3_analyzer/{trace_reader,reference,differ,reporter}/
│   └── l4_cli/
├── runtime/                  # L2 C/C++:hook/ dma/ trace_writer/
├── stubs/                    # stub header
├── rules/{hardware_macros,operator_interfaces}/, isomorphisms.py, blacklist.py
├── tests/{fixtures,unit,integration}/
└── examples/
```

> 按 KISS,目录随各层落地逐步创建,不一次性铺空壳。V0 只创建 L1 + 用到的部分。
