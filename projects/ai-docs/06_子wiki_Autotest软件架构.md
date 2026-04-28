# 子 Wiki 6：Autotest 软件架构（领域分层与扩展点）

> **本文档定位：** Autotest 跨平台软件架构 —— 领域分层、端口接口、PlatformAdapter 抽象、pytest 编排、meta-testing。
>
> **与其它文档的分工：**
> - [子 Wiki 5](./05_子wiki_多执行平台架构扩展.md)：**需求视角** —— 平台职责、FR/NFR、验收标准
> - 本文档（6）：**架构视角** —— 跨平台代码怎么分层
> - [子 Wiki 6B](./06b_子wiki_原型测试环境详设.md)：**FPGA 平台落地详设** —— 桩 CPU、A/B 双交互机制、buffer / 状态机。是本文档 `FpgaAdapter` 的内部展开
>
> **编码规范以全局 `CLAUDE.md` 为准**（函数 < 50 行、类型标注、枚举替代魔法字符串等），本文档只讲架构。

---

## 目录

0. [Autotest 核心定位](#0-autotest-核心定位)
1. [现状与扩展驱动](#1-现状与扩展驱动)
2. [架构原则](#2-架构原则)
3. [领域分层](#3-领域分层)
4. [端口接口](#4-端口接口)
5. [新增平台流程](#5-新增平台流程)
6. [与 PAL 的关系](#6-与-pal-的关系)
7. [演进路线](#7-演进路线)
8. [pytest 主体融入分层](#8-pytest-主体融入分层)
9. [Autotest 自身测试（meta-testing）](#9-autotest-自身测试meta-testing)
10. [常见问题](#10-常见问题)

---

## 0. Autotest 核心定位

Autotest 同时做两件事：

### 0.1 测试框架驱动（pytest 主体）

用例的**发现 / 参数化 / 调度 / 并行 / 报告**全部由 pytest 承担：markers、fixture、parametrize、xdist、超时、重试、归档；平台路由按 `--platform` 选择 adapter。详见 § 8。

### 0.2 组合调用桩 CPU 原子能力

各平台底层暴露**基础原子能力**：FPGA 平台是 [桩 CPU 的 svc 函数集](./06b_子wiki_原型测试环境详设.md)（数据传输、模型加载、启动 / 等结果、比数控制、DFX 读、日志导出），EMU 是自有 Python API，link / rtl2c 是脚本，EDA 是打包命令。

**Autotest 的核心增值是把原子能力组合成业务级动作** —— 「跑一个用例」 = `setup → upload_input/golden → load_do → start_model → wait_result → compare → archive`。同一份用例代码跨平台复用，靠 `PlatformAdapter` 把业务动作翻译为各平台原子能力调用。

### 0.3 要素 → 落点对照

| 要素 | 落在哪 |
|---|---|
| 主流程编排（用例发现 / 调度 / 并行）| pytest fixture + parametrize（§ 8）|
| 业务级动作（dump / 切换 / 自动回落 / 首发散定位 / DFX 裁决）| 能力服务层（§ 3 ②）|
| 原子能力封装（具体平台 IO）| PlatformAdapter 实现（§ 3 ③）|
| 跨平台一致性 | `typing.Protocol` 端口接口（§ 4）|
| 裁决与归档 | 三态 `Verdict` + 报告（对接 [03](./03_子wiki_业务结果确认.md) / [07](./07_子wiki_验证报告模板.md)）|

> 一句话：**Autotest = pytest 主体编排 + 跨平台原子能力组合**。FPGA 平台原子能力清单见 [06B § 4.6](./06b_子wiki_原型测试环境详设.md)。

---

## 1. 现状与扩展驱动

**现状：** Autotest 当前只跑通 FPGA 上板这一条链路（RDO 串口、CPU 桩、接口 FPGA 消息），link / rtl2c / EMU / EDA 尚未接入。

**扩展驱动：** EMU 是性能权威出口、link 是准入闸门、rtl2c 提供波形、EDA 仅打包交付。详情见 [子 Wiki 5](./05_子wiki_多执行平台架构扩展.md)。

**为何先做架构优化：** 在现有 FPGA 代码里铺 if-else 加平台分支，会把业务逻辑和平台细节纠缠在一起 —— 改一处比对要动五处分支，新平台接入成本线性增长，回归难度指数增长。**必须先用分层 + 依赖倒置把"业务逻辑"和"平台接入"隔离。**

---

## 2. 架构原则

1. **稳定内核：** 核心业务概念（用例 / 版本 / 裁决）与技术实现解耦，不依赖任何平台
2. **依赖单向：** 外层依赖内层，内层不感知外层
3. **扩展点单一：** 新增平台只动最外层 adapter，不改核心与服务
4. **能力服务跨平台复用：** 精度比对、dump 策略、用例切换写一次，多平台复用
5. **pytest 编排：** 主流程用 pytest 装饰器 + fixture + markers 承载（详见 § 8）
6. **不做向后兼容 dead code：** 删代码彻底删，不留 `_deprecated_xxx`、不为"未来可能"预留 hook
7. **抽象有代价：** 3+ 使用点才抽公共函数，2+ 实际需求才抽端口接口，够用为止

> 编码细节（函数长度、类型标注、命名、枚举、异常）以全局 `CLAUDE.md` 为准，本文档不复述。

---

## 3. 领域分层

### 3.1 三层模型

```
┌─────────────────────────────────────────────┐
│  ③ 平台适配（Platform Adapters）             │ ← 最易变
│  fpga / link / rtl2c / emu / eda            │   扩展点在这里
└────────────────┬────────────────────────────┘
                 │ 依赖端口接口（向内）
┌────────────────▼────────────────────────────┐
│  ② 能力服务（Capability Services）           │
│  精度比对 · dump 策略 · 用例切换 ·           │
│  自动回落 · DFX 裁决 · 首发散定位            │
└────────────────┬────────────────────────────┘
                 │ 依赖领域对象（向内）
┌────────────────▼────────────────────────────┐
│  ① 核心领域（Domain）                        │ ← 最稳定
│  Case · Baseline · Verdict · CompareMode · │
│  SwitchStrategy · BizSwVersion              │
└─────────────────────────────────────────────┘
```

### 3.2 每层职责

| 层 | 组件 | 约束 |
|---|---|---|
| ① 核心领域 | `Case`、`Baseline`、`Verdict`、`CompareMode`（END_TO_END / STAGE_COMPARE）、`SwitchStrategy`（SOFT / MEDIUM / HARD）、`BizSwVersion` | **零技术依赖** —— 只表达业务概念，不碰 IO / 网络 / 文件 |
| ② 能力服务 | `PrecisionCompareService`、`DumpStrategy`、`CaseSwitcher`、`AutoFallback`（端到端→阶段性回落）、`DivergenceLocator`、`DfxJudge` | 依赖端口接口调平台能力，**不感知具体平台** |
| ③ 平台适配 | `FpgaAdapter`、`EmuAdapter`、`LinkAdapter`、`Rtl2cAdapter`、`EdaAdapter` | 实现端口接口；平台专属逻辑（RDO 串口、EMU API、LAVA、espi、TESGINE）只在此层 |

**领域对象用 `@dataclass(frozen=True)`** —— 不可变，杜绝跨层意外修改。**枚举替代魔法字符串**、**异常分层**（`AutotestError` → `PlatformError` / `PlatformTimeoutError` / `VersionMismatchError`），具体写法以全局规范为准。

### 3.3 典型调用链

精度用例「读某阶段中间张量」：

```
CaseRunner (pytest fixture + 编排)
    ↓
DumpStrategy.stage_compare(case, stages=[...])
    ↓
TensorReader.read(stage_id)         ← 端口接口
    ↓
FpgaTensorReader / LinkTensorReader / EdaTensorReader   ← ③ adapter 实现
```

① / ② 层不感知最终走哪个 adapter；③ 层把平台细节完全封装。

---

## 4. 端口接口

能力服务对外依赖一组**端口接口**，由平台适配层实现。**用 `typing.Protocol` 不用 ABC** —— 鸭子类型原生、不强制继承、加 `@runtime_checkable` 可运行时校验。

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class PlatformAdapter(Protocol):
    def load_version(self, baseline: Baseline) -> None: ...
    def start_business(self, case: Case) -> StartResult: ...
    def trigger_stimulus(self) -> None: ...
    def query_status(self) -> Status: ...
    def switch_case(self, next_case: Case, strategy: SwitchStrategy) -> None: ...

class TensorReader(Protocol):
    def read(self, stage_id: str) -> Tensor: ...

class CompareExecutor(Protocol):
    def run_standard(self, case: Case) -> Verdict: ...     # 接口 FPGA 硬件比对
    def run_fallback(self, case: Case) -> Verdict: ...     # CPU 桩 dump + compare 模块
    def available_paths(self) -> list[str]: ...

class ResultSink(Protocol):
    def archive(self, case_id: str, artifacts: Artifacts) -> None: ...

class RegisterReader(Protocol):
    def read_dfx(self, regs: list[str]) -> DfxSnapshot: ...
```

**约束：**
- 领域 / 服务层只引接口，不引具体 adapter
- 端口参数 / 返回值都是**领域对象**（`Case`、`Verdict`、`Tensor`），不返回平台原生类型（如 RDO 消息、EMU API 返回值）
- 端口接口应稳定 —— 频繁变动说明抽象漏了

---

## 5. 新增平台流程

假设新增 `EmuAdapter`：

1. `adapters/emu_adapter.py` 实现所有端口接口
2. `adapters/__init__.py` 注册：`ADAPTERS["emu"] = EmuAdapter`
3. 平台配置声明支持：`platforms: [fpga, emu]`
4. 跑 adapter 单测（mock 其它层）
5. 跑既有用例在 emu 上的端到端验证

**零修改：** 核心领域、能力服务、主流程、报告模板。

### 5.1 Adapter 内部允许做的

- 调平台原生接口（EMU Python 绑定、RDO 串口、LAVA REST、espi / TESGINE）
- 平台数据格式 ↔ 领域对象（TESGINE 流 ↔ `Tensor`，接口 FPGA 消息 ↔ `Verdict`）
- 平台资源管理（板锁、EMU 实例池、网页调度服务）

### 5.2 Adapter 内部禁止做的

- 精度比对（属能力服务层）
- 裁决逻辑（属核心领域）
- 与其它平台交叉引用
- 反向 import 能力服务模块

---

## 6. 与 PAL 的关系

子 Wiki 5 的 **PAL** = 本文档 § 4 端口接口 + § 3 平台适配层。同一概念两种视角：PAL 看「多平台扩展」，领域分层看「代码组织」。

---

## 7. 演进路线

| 阶段 | 工作 | 验收 |
|---|---|---|
| **0 重构** | 现有 FPGA 代码分层；抽 `PlatformAdapter` 等端口接口 | 既有用例照常跑通 |
| **1 link + rtl2c** | 新增对应 adapter；接入 4.9 流水线 link ‖ rtl2c 并行段 | link 准入闸门、rtl2c 波形导出 |
| **2 EMU** | 新增 `EmuAdapter`，直接 import EMU 自有 Python API；接入性能 + 诊断分支 | 性能出口闭环、checkpoint / replay 验证 |
| **3 EDA** | 新增 `EdaAdapter`（只打包，不执行） | 自动打包上传 |
| **4 调度并行** | 资源调度服务（对标 LAVA） + `pytest-xdist` 并行 | 多板 / 多 emu 并行 |

> 与 [子 Wiki 5 · 第 6 章](./05_子wiki_多执行平台架构扩展.md) 阶段编号对应：05 的"阶段 5 跨平台一致性闭环"是本表阶段 4 完成后的整体验收，不产生新的代码结构改动。

---

## 8. pytest 主体融入分层

主流程用 pytest 编排（详见主文档 4.4.6）。pytest 不是一层，而是**编排机制**，跨三层使用但不破坏分层约束。

### 8.1 pytest 机制 vs 分层

| pytest 机制 | 分层位置 | 作用 |
|---|---|---|
| 用例函数 `def test_xxx` | 领域实例化 | 一个 pytest 用例 = 一个 `Case` 实例 |
| `@pytest.mark.parametrize` | 领域实例化 | 启动矩阵每行 → parametrized 用例 |
| `conftest.py` + fixture | 能力服务调度层 | 组装能力服务与 adapter |
| 自定义 markers (`@accuracy` / `@perf` / `@l0`) | 领域元数据 | 用例分类（替代自建 type 字段）|
| `pytest-xdist` | 基础设施层 | 多板并行 |
| `pytest_runtest_setup/teardown` | 能力服务调度层 | 切换点快照、DFX、归档接入 |

### 8.2 架构挂点

仅列**架构相关**的两个 hook，其余 pytest 用法以官方文档为准。

- **`pytest_runtest_teardown` 切换钩子** —— 落实主文档 4.7 切换策略：`SwitchStrategy.HARD → fpga_reset()`、`MEDIUM → swap_biz_sw()`
- **`pytest_collection_modifyitems` 动态过滤** —— 按 `--platform` 参数将 `fpga_only` marker 在非 fpga 平台自动 skip

```python
def pytest_runtest_teardown(item, nextitem):
    if nextitem is None:
        return
    strategy = decide_switch(item, nextitem)
    if strategy is SwitchStrategy.HARD:
        fpga_reset()
    elif strategy is SwitchStrategy.MEDIUM:
        swap_biz_sw(nextitem)
```

---

## 9. Autotest 自身测试（meta-testing）

Autotest 一旦有 bug，所有用例结果都不可信。本章讲怎么测 Autotest 自己。

### 9.1 测试金字塔

| 层 | 测什么 | 工具 / 实现 | 覆盖率目标 |
|---|---|---|---|
| **单元（多）** | 核心领域纯逻辑；能力服务（`AutoFallback`、`DivergenceLocator` 等）配 mock adapter | `pytest` + `unittest.mock` 或手写 `FakeAdapter`，总时长 < 30s | 领域 ≥ 90% line / 服务 ≥ 80% line+branch |
| **契约（中）** | 同一套测试对每个 adapter 跑一遍，确认实现符合端口语义 | 参数化 fixture `params=[FpgaAdapter, LinkAdapter, ...]` | 覆盖所有端口方法 |
| **端到端（少）** | `DummyAdapter` 返回确定性假数据，验证 Autotest 流程逻辑（首用例策略、自动回落、切换策略） | 行为断言 | 覆盖 4.9 流水线全部分支 + 自动切换 |

**契约测试关键点：** 同一套测试对每个 adapter 跑一遍 —— 新增 adapter 自动覆盖，违约实现立刻被捕获，不必等整轮回归。

**DummyAdapter 范例：**

```python
class DummyAdapter:
    def __init__(self, verdict_plan: list[Verdict]):
        self._verdict_plan = list(verdict_plan)
    def load_version(self, baseline): pass
    def start_business(self, case): return StartResult(ready=True)
    def compare(self, golden) -> Verdict: return self._verdict_plan.pop(0)
    # ... 其余 no-op 实现
```

### 9.2 CI 接入

Pre-submit CI（lint + meta 单元 + meta 契约 + meta 端到端 Dummy）必过且秒级，**不依赖真实硬件**；Post-merge CI 才跑 link / fpga / rtl2c / emu 真实平台（按 00 · 4.9）。每个 PR 都能保证框架自身没被改坏。

### 9.3 边界

只保证「**框架代码自己没 bug**」 —— 不测 pytest、CMC / LAVA / EMU API 客户端、真实硬件行为。

---

## 10. 常见问题

| 问题 | 解答 |
|---|---|
| 资源调度（LAVA / 网页服务）算哪一层？ | 基础设施层（与 adapter 同级），用端口接口暴露给能力服务 |
| 比数标准 / 备选路径算哪一层？ | 端口接口 `CompareExecutor`；每个 adapter 自实现两条路径，能力服务按环境自选（见子 Wiki 2 · 4.1）|
| 和子 Wiki 5（PAL）重复吗？ | 不重复。05 需求视角，本文档实现视角 |
