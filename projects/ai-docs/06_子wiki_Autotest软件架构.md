# 子 Wiki 6：Autotest 软件架构（领域分层与扩展点）

> 本子 Wiki 描述 Autotest 的软件设计模式与分层架构，是平台扩展（EMU、link、rtl2c、eda 联动）的**设计基础**。
>
> 对应主文档 [第 2.2 节](./00_主文档_AI验证整体执行流程.md)（架构简述）。主文档聚焦业务验证流程与 Autotest 实操，本文档聚焦**架构与设计模式**。
>
> **与子 Wiki 5 的分工：** 子 Wiki 5 回答"**需要什么、为什么需要**"（需求分析），本文档回答"**代码怎么组织**"（软件模块设计）。详细业务需求（各平台职责、FR / NFR、使用场景、验收标准）见 [子 Wiki 5](./05_子wiki_多执行平台架构扩展.md)，本文档不重复需求层描述。

---

## 目录

1. [现状评估](#1-现状评估)
2. [架构优化原则](#2-架构优化原则)
3. [领域分层详解](#3-领域分层详解)
4. [端口接口定义（核心扩展点）](#4-端口接口定义核心扩展点)
5. [新增平台的标准接入流程](#5-新增平台的标准接入流程)
6. [与 PAL 的关系](#6-与-pal-的关系)
7. [从单 FPGA 到多平台的演进路线](#7-从单-fpga-到多平台的演进路线)
8. [pytest 主体如何融入分层](#8-pytest-主体如何融入分层)
9. [常见问题](#9-常见问题)

---

## 1. 现状评估

### 1.1 Autotest 当前只支持 FPGA 调试

当前 Autotest 只跑通 FPGA 原型（上板）这一条链路：

- RDO 串口 / 文件通道已打通
- CPU 桩交互、接口 FPGA 消息下发已闭环
- 对 link / rtl2c / emu / eda 的接入**尚未开始**

### 1.2 扩展需求（业务驱动）

| 平台 | 扩展必要性 | 为什么必须 | 接入可行性 |
|---|---|---|---|
| **EMU** | **必须** | FPGA 测性能不准，EMU 是性能用例权威出口；FPGA 失败时 EMU 是诊断手段 | **EMU 自有 API 提供 Python 接口**，可直接 import 集成到 pytest 主体，不需要跨语言桥接 |
| **link**（功能仿真）| 必须 | 准入闸门，卡住不合格版本省 FPGA 板级资源 | LINKST 一次性下发 + 离线日志 |
| **rtl2c** | 必须 | 波形导出（FPGA 无此能力），用于失败定位 | 脚本 + 工具链调用 |
| **eda** | 必须 | 打包上传供人手动波形分析（不执行，只交付）| 仅打包交付，无运行时接入 |

### 1.3 为什么必须先做架构优化

平铺式加代码（在现有 FPGA 代码里插 if-else 分支）会导致：

- **业务逻辑和平台细节纠缠**：改一处精度比对要改五处平台分支
- **新平台接入成本线性增长**：每加一个平台都要动主流程
- **回归难度指数增长**：任何主流程改动都要回归所有平台

**必须通过分层 + 依赖倒置把"业务逻辑"和"平台接入"隔离。**

---

## 2. 架构优化原则

1. **稳定内核**：核心业务概念（用例 / 版本 / 裁决）与技术实现解耦，不依赖任何平台
2. **依赖方向单向**：外层依赖内层，内层不感知外层
3. **扩展点单一**：新增平台只动最外层 adapter，不改核心与服务
4. **能力服务跨平台**：精度比对、dump 策略、用例切换等逻辑**写一次、多平台复用**，而不是每个平台一套
5. **pytest 主体**：整个主流程用 pytest 编排，装饰器 + fixture + markers 承载超时 / 参数矩阵 / 用例分类（详见主文档 4.4.6）
6. **代码规范（clean code）**：
   - 函数 **< 50 行**，超了拆 helper
   - 所有公开函数必须有**完整类型标注**；`Optional[X]` 不写 `X | None`（清晰、跨版本兼容）；返回类型精确（`tuple[int, int]` 而不是 `tuple[int, ...]`）
   - **命名表意图不表实现**（`dump_final_tensor` 而不是 `process`、`get_x`）
   - **默认不写注释**；只在 WHY 非显而易见时写（隐藏约束、绕 bug、反直觉选择），注释内容必须和代码一致（改代码同步改注释）
   - **只在系统边界做防御**（CLI / 网络 / 文件入口）；内部函数信任类型标注，不做重复 `isinstance` 校验
   - **枚举替代魔法字符串**（`CompareMode.END_TO_END` 而不是 `"end_to_end"`）
7. **不做向后兼容的 dead code**：删代码**彻底删**，不留 `_deprecated_xxx`、不加 `# removed` 注释，git 历史保留该保留的；不为"未来可能有的平台"预留不落地的 hook
8. **只在 3+ 使用点抽公共函数，2+ 实际需求抽端口接口**——抽象有代价，够用为止

---

## 3. 领域分层详解

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
│  用例 · 版本基线 · 裁决结果 · 比数模式 ·      │
│  比数策略 · 业务软件版本 · 首用例             │
└─────────────────────────────────────────────┘

依赖方向：外层 → 内层；内层不感知外层
```

### 3.2 每层职责

| 层 | 组件示例 | 约束 |
|---|---|---|
| ① 核心领域 | `Case`、`Baseline`、`Verdict`、`CompareMode`（端到端 / 阶段性）、`BizSwVersion`（初级 / 进阶 / 商用）、`SwitchStrategy`（软 / 中 / 硬切换） | **零技术依赖**——只表达业务概念，不碰 IO / 网络 / 文件 |
| ② 能力服务 | `PrecisionCompareService`（bit 级 + 辅助分析）、`DumpStrategy`、`CaseSwitcher`、`AutoFallback`（端到端→阶段性回落）、`DivergenceLocator`（首发散阶段定位）、`DfxJudge` | 依赖端口接口调用平台能力，**不感知具体平台** |
| ③ 平台适配 | `FpgaAdapter`、`EmuAdapter`、`LinkAdapter`、`Rtl2cAdapter`、`EdaAdapter` | 实现端口接口；所有平台专属逻辑（RDO 串口、EMU API、LAVA 资源调度、espi、TESGINE）都在此层 |

**领域对象用 `@dataclass(frozen=True)`**：不可变，杜绝跨层传递时的意外修改；`field(default_factory=list)` 避开可变默认值坑：

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Case:
    case_id: str
    markers: list[str] = field(default_factory=list)
    execution_mode: str = "hw_optimized"    # 用枚举更好，见下
    stages: list["Stage"] = field(default_factory=list)
```

**枚举替代魔法字符串**（在原则 2.6 中已声明，这里落到具体对象）：

```python
from enum import Enum

class CompareMode(Enum):
    END_TO_END = "end_to_end"
    STAGE_COMPARE = "stage_compare"

class Verdict(Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
```

**异常分层**（跨三层共享）：

```python
class AutotestError(Exception):
    """所有业务异常的基类"""

class PlatformError(AutotestError): ...           # 平台侧错误（adapter 抛）
class PlatformTimeoutError(PlatformError): ...    # 可重试
class VersionMismatchError(AutotestError): ...    # 立刻停止，别重试
```

使用端按层级 catch，让"可重试 / 不可重试 / 走诊断"三条路径从类型上区分，而不是 if-else 字符串判断。别用 `raise Exception("xxx")` —— 异常类层次本身是文档。

### 3.3 典型调用链示例

**精度用例执行"读取某阶段中间张量"的调用链：**

```
CaseRunner (pytest fixture + 编排)
    ↓
DumpStrategy.stage_compare(case, stages=[backbone_out, ...])
    ↓
TensorReader.read(stage_id)         ← 端口接口
    ↓
FpgaTensorReader (③ adapter) → 走 CPU 桩 dump
或
LinkTensorReader (③ adapter) → 调仿真发布版 dump 接口
或
EdaTensorReader  (③ adapter) → 从波形文件抓取
```

- ① / ② 层**不感知**最终走哪个 adapter
- ③ 层把平台细节完全封装

---

## 4. 端口接口定义（核心扩展点）

能力服务对外依赖一组 **端口接口（Ports）**，由平台适配层实现。**用 `typing.Protocol` 定义，不用抽象基类**——鸭子类型原生、不强制继承、旧代码加完类型标注即可用；加 `@runtime_checkable` 还能支持 `isinstance()` 运行时校验。

以下是核心接口草稿（命名和签名实际实现可调）：

```python
from typing import Protocol, runtime_checkable

# 平台整体适配接口
@runtime_checkable
class PlatformAdapter(Protocol):
    def load_version(self, baseline: Baseline) -> None: ...
    def start_business(self, case: Case) -> StartResult: ...
    def trigger_stimulus(self) -> None: ...
    def query_status(self) -> Status: ...
    def switch_case(self, next_case: Case, strategy: SwitchStrategy) -> None: ...

# 中间张量读取（阶段性比数 / 调试 dump 使用）
class TensorReader(Protocol):
    def read(self, stage_id: str) -> Tensor: ...

# 比数执行路径（对应子 Wiki 2 · 4.1 的两条路径）
class CompareExecutor(Protocol):
    def run_standard(self, case: Case) -> Verdict: ...     # 接口 FPGA 硬件比对
    def run_fallback(self, case: Case) -> Verdict: ...     # CPU 桩 dump + compare 模块
    def available_paths(self) -> list[str]: ...            # 当前环境可用路径

# 结果归档
class ResultSink(Protocol):
    def archive(self, case_id: str, artifacts: Artifacts) -> None: ...

# DFX 寄存器读取
class RegisterReader(Protocol):
    def read_dfx(self, regs: list[str]) -> DfxSnapshot: ...
```

### 4.1 端口接口的设计约束

- **领域 / 服务层只用接口**，不引用具体 adapter
- **适配层只实现接口**，把平台细节封装在内部
- 端口接口的参数、返回值都用**领域对象**（`Case`、`Verdict`、`Tensor`），不用平台原生类型（不返回 RDO 消息、EMU API 返回值）
- 端口接口应稳定 —— 频繁变动说明抽象漏了，需要重新审视

---

## 5. 新增平台的标准接入流程

### 5.1 步骤

假设新增 `EmuAdapter`：

1. 在 `adapters/` 下新建 `emu_adapter.py`
2. 实现所有端口接口（`PlatformAdapter`、`TensorReader`、`CompareExecutor`、`ResultSink`、`RegisterReader`）
3. 在 `adapters/__init__.py` 注册：`ADAPTERS["emu"] = EmuAdapter`
4. 在平台配置中声明支持：`platforms: [fpga, emu]`
5. 跑针对 adapter 的单元测试（mock 其它层）
6. 跑一次已有用例在 emu 上的端到端验证

**不需要修改的地方**：核心领域、能力服务、主流程编排、报告模板 —— 全部零修改。

### 5.2 Adapter 内部**允许**做什么

- 调用平台原生接口：
  - **EMU**：直接 `import` EMU 自有 API 的 Python 绑定，调用 espi / TESGINE 控制接口
  - **FPGA**：RDO 串口、CPU 桩文件通道
  - **link / rtl2c / eda**：各自脚本 / 工具链
  - 资源调度：LAVA REST API / 自建网页调度服务
- 平台专属数据格式转换（TESGINE 流 ↔ Tensor 领域对象；接口 FPGA 消息 ↔ Verdict）
- 平台专属资源管理（板级锁、EMU 实例池、网页调度服务对接）

**资源获取 / 释放用上下文管理器**（`@contextmanager` 或 pytest fixture），避免在 setup / teardown 手动配对：

```python
from contextlib import contextmanager

@contextmanager
def fpga_session(baseline):
    adapter = FpgaAdapter()
    adapter.load_version(baseline)
    try:
        yield adapter
    finally:
        adapter.cleanup()            # 即使异常也清理

# pytest fixture 版本
@pytest.fixture
def fpga(baseline):
    adapter = FpgaAdapter()
    adapter.load_version(baseline)
    yield adapter                    # 用例在此处运行
    adapter.cleanup()
```

**路径一律用 `pathlib.Path`**（不用 `os.path.join`）：

```python
from pathlib import Path
ARCHIVE_ROOT = Path("/archive")
archive_path = ARCHIVE_ROOT / build / case_id / "report.json"
```

**昂贵加载用 `@cached_property` / `@lru_cache`**：

```python
from functools import cached_property, lru_cache

class Baseline:
    @cached_property
    def manifest(self) -> dict:
        return yaml.safe_load(self.manifest_path.read_text())

@lru_cache(maxsize=128)
def load_golden(path: Path) -> Tensor:
    return np.load(path)
```

**CLI 入口用 `typer` 或 `click`**（不手搓 argparse）：

```python
import typer
app = typer.Typer()

@app.command()
def run(case_id: str, platform: str = "fpga", mode: CompareMode = CompareMode.END_TO_END):
    """执行单个用例"""
    ...
```

### 5.3 Adapter 内部**禁止**做什么

- 精度比对（属于能力服务层）
- 裁决逻辑（属于核心领域）
- 与其它平台的交叉引用（平台间必须解耦）
- 导入能力服务模块（反向依赖会把分层打穿）

---

## 6. 与 PAL 的关系

[子 Wiki 5](./05_子wiki_多执行平台架构扩展.md) 定义的 **平台抽象层（PAL）** 对应本文档的：

- PAL **接口定义** = 本文档第 4 节的**端口接口**
- PAL **各平台实现** = 本文档第 3 节的 **③ 平台适配层**

两者是同一概念：PAL 是外部叫法（从"多平台扩展"视角看），领域分层是内部实现视角（从"代码如何组织"视角看）。

---

## 7. 从单 FPGA 到多平台的演进路线

### 7.1 阶段 0：重构现有 FPGA 代码为三层

**目标**：在不增加平台的前提下，先把现有代码分层

- 平台专属代码（RDO 交互、接口 FPGA 消息）收到 `fpga_adapter` 内
- 比数 / 切换 / 裁决等通用逻辑抽到能力服务层
- 用例 / 版本 / 裁决结果等定义到核心领域层
- 抽出端口接口（`PlatformAdapter` 等）

**验收**：单 FPGA 平台所有既有用例照常跑通，代码结构清晰。

### 7.2 阶段 1：接入 link + rtl2c

- 新增 `LinkAdapter`、`Rtl2cAdapter`
- 接入主文档 4.9 流水线的 link ‖ rtl2c 并行阶段
- 验证 link 准入闸门 + rtl2c 波形导出

### 7.3 阶段 2：接入 EMU（性能出口 + 诊断）

- 新增 `EmuAdapter`：**直接 import EMU 自有 API 的 Python 绑定**（espi / TESGINE 控制），无需跨语言 bridge
- pytest fixture 里用 Python API 起 EMU 实例、灌激励、读结果，adapter 负责把原生返回值转成领域对象（`Case` / `Verdict` / `Tensor`）
- 接入主文档 4.9 流水线的 EMU 性能阶段 + EMU 诊断分支
- 验证性能出口和诊断闭环；同时验证 EMU 的 checkpoint / replay 能力（见主文档 4.9.3）

### 7.4 阶段 3：接入 EDA（打包交付）

- 新增 `EdaAdapter`（只打包上传，不执行用例）
- 接入主文档 4.9 流水线的 EDA 自动打包分支

### 7.5 阶段 4：资源调度 / pytest-xdist 并行

- 资源调度服务（对标 LAVA，见主文档 4.7.5）作为基础设施层的兄弟模块
- `pytest-xdist` 多板 / 多 emu 实例并行执行

> 本章阶段编号（0~4）与 [子 Wiki 5 · 第 6 章](./05_子wiki_多执行平台架构扩展.md) 的验收阶段（0~5）对应关系：05 的"阶段 5 跨平台一致性闭环"是本章阶段 4 完成后的整体验收动作，不额外产生代码结构改动。

---

## 8. pytest 主体如何融入分层

Autotest 主体是 pytest（见主文档 4.4.6）。pytest 本身不是一层，而是**主流程编排的机制**；它跨三层使用但不破坏分层约束。

### 8.1 pytest 机制与分层对照

| pytest 机制 | 对应分层位置 | 说明 |
|---|---|---|
| 用例函数（`def test_xxx(...)`）| 领域实例化 | 一个 pytest 用例 = 一个 `Case` 领域对象的实例 |
| `@pytest.mark.parametrize` | 领域实例化 | 启动矩阵每行 → 一个 parametrized 用例 |
| `conftest.py` + fixture | 能力服务调度层 | fixture 组装能力服务与 adapter |
| 自定义 markers（`@accuracy` / `@perf` / `@l0`）| 领域元数据 | 承载用例类型与分类（替代自建 type 字段）|
| `pytest-xdist` | 基础设施层 | 多板并行 |
| `pytest_runtest_setup/teardown` | 能力服务调度层 | 切换点快照、DFX 查询、归档接入点 |

### 8.2 parametrize：`ids=` 让用例名可读

```python
matrix = [
    ("proto_v1", "resnet50",  "spec_mini"),
    ("proto_v1", "resnet50",  "spec_full"),
    ("proto_v2", "bert_base", "spec_full"),
]

@pytest.mark.parametrize(
    "proto,model,spec",
    matrix,
    ids=lambda p: "_".join(p),
)
def test_accuracy(proto, model, spec, fpga):
    ...
```

生成的用例名是 `test_accuracy[proto_v1_resnet50_spec_mini]`，不是 `test_accuracy[matrix0]`。

### 8.3 indirect=True：把参数喂给 fixture

```python
@pytest.fixture
def platform(request):
    return ADAPTERS[request.param]()

@pytest.mark.parametrize("platform", ["fpga", "emu"], indirect=True)
def test_perf(platform):
    ...
```

"参数名 → adapter 实例"的转换封装在 fixture，用例签名直接拿就绪对象。

### 8.4 fixture 分层 scope：session / module / function

```python
@pytest.fixture(scope="session")     # 整个 pytest run 一次
def cmc_client(): ...

@pytest.fixture(scope="module")      # 每个测试文件一次
def baseline(cmc_client): ...

@pytest.fixture(scope="function")    # 每个用例一次（默认）
def fresh_dir(tmp_path): ...
```

**重资源放 session / module，轻资源放 function**。FPGA adapter 的实例化属于 module；一次板级复位后的 case 上下文属于 function。

### 8.5 参数化 fixture：天然跨平台用例

```python
@pytest.fixture(params=["fpga", "link", "rtl2c", "emu"])
def platform(request):
    return ADAPTERS[request.param]()

def test_bit_exact(platform):
    # 同一个用例自动跑 4 次，每平台一次
    ...
```

这正是子 Wiki 5 FR-3 跨平台 bit-exact 用例的标准写法。

### 8.6 autouse fixture：横切关注点

```python
@pytest.fixture(autouse=True)
def _dfx_snapshot(request):
    dfx_clear()
    yield
    dfx_dump(request.node.nodeid)
```

自动应用到所有用例，不需要每个用例手动依赖。DFX 查询、切换点快照、日志记录这类横切放这里。

### 8.7 conftest.py 层级隔离

```
tests/
├── conftest.py                  # 全局 fixture（baseline、cmc_client）
├── accuracy/
│   ├── conftest.py              # 精度用例专用（golden 加载）
│   └── test_cv.py
└── perf/
    ├── conftest.py              # 性能用例专用（[PERF] 日志解析器）
    └── test_resnet_perf.py
```

fixture 按目录可见性下传。把"只有某类用例需要"的 fixture 放到对应 conftest，避免全局 conftest 臃肿。

### 8.8 marker 注册 + strict

```python
# conftest.py
def pytest_configure(config):
    for m in [
        "accuracy: 精度用例",
        "perf:     性能用例",
        "l0:       L0 冒烟",
        "首用例:   CPU 简化实现的首用例",
        "fpga_only: 只在 fpga 平台跑",
    ]:
        config.addinivalue_line("markers", m)
```

配 `pytest --strict-markers`：未注册 marker 直接报错，防拼写错。

### 8.9 `pytest_collection_modifyitems`：平台感知的动态过滤

```python
def pytest_collection_modifyitems(config, items):
    current = config.getoption("--platform")
    skip = pytest.mark.skip(reason=f"不支持平台 {current}")
    for item in items:
        markers = {m.name for m in item.iter_markers()}
        if "fpga_only" in markers and current != "fpga":
            item.add_marker(skip)
```

不用改用例代码就实现了"平台感知的用例收集"。

### 8.10 `pytest_runtest_setup/teardown`：切换策略挂钩

```python
def pytest_runtest_teardown(item, nextitem):
    if nextitem is None:
        return
    strategy = decide_switch(item, nextitem)   # 软 / 中 / 硬
    if strategy is SwitchStrategy.HARD:
        fpga_reset()
    elif strategy is SwitchStrategy.MEDIUM:
        swap_biz_sw(nextitem)
```

主文档 4.7 切换策略的自动化实现点。

### 8.11 超时装饰器栈（对应主文档 4.4.5）

```python
@pytest.mark.timeout(600)                 # 用例级（pytest-timeout 插件）
@stage_timeout(do_load=60, stimulus=30)   # 阶段级（自定义装饰器）
def test_accuracy(case, fpga):
    ...
```

优先级：**用例级 > 阶段级 > 全局（pytest.ini）**。

### 8.12 自带 fixture：`tmp_path` / `monkeypatch` / `caplog`

```python
def test_archive(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ARCHIVE_ROOT", str(tmp_path))
    with caplog.at_level("INFO"):
        archive_case(case)
    assert (tmp_path / case.case_id / "report.json").exists()
    assert "archived" in caplog.text
```

少写 mock，少造临时文件，`caplog` 直接断言日志。

### 8.13 并行执行（pytest-xdist）

```bash
pytest -n auto                   # 按 CPU 核数
pytest -n 4 --dist=loadfile      # 每 worker 抓整个文件（同文件串行）
```

配合资源调度服务（LAVA 或等价），每个 worker 从调度服务取一块板跑用例。

### 8.14 报告

- `pytest --html=report.html --self-contained-html`：单文件 HTML
- `pytest --alluredir=reports/` + `allure serve reports/`：交互式 UI；fixture 里 `allure.attach(...)` 把 dump 贴到用例详情
- `pytest --junitxml=report.xml`：CI 消费

### 8.15 插件封装（非必要不写）

```python
# pytest_autotest_platform.py
def pytest_addoption(parser):
    parser.addoption("--platform", default="fpga",
                     choices=["fpga", "link", "rtl2c", "emu"])

@pytest.fixture
def adapter(request):
    return ADAPTERS[request.config.getoption("--platform")]()
```

**先在 conftest.py 里写，顺手了再抽成 plugin**（`pyproject.toml` 注册 entry point，让多项目共用）。

---

## 9. 常见问题

| 问题 | 解答 |
|---|---|
| 新增平台要不要改核心领域？ | 不要。如果必须改，说明抽象泄漏了，重新审视哪个领域对象被污染 |
| Adapter 内部可以直接调能力服务吗？ | 不可以。反向依赖会把层打穿；能力服务只能被更外层（runner / app）调用 |
| 资源调度（LAVA / 网页服务器）算哪一层？ | 基础设施层（与 adapter 同级），使用端口接口暴露给能力服务 |
| 比数执行路径（标准 / 备选）算哪一层？ | 端口接口抽象（`CompareExecutor`）；**每个 adapter 各自实现两条路径**，能力服务按环境自动选（见子 Wiki 2 · 4.1）|
| 测试 Autotest 本身的正确性怎么办？ | 核心领域和能力服务用单元测试（mock adapter）；adapter 用契约测试（针对端口接口）；端到端用用例集回归 |
| 和子 Wiki 5（PAL）是否重复？ | 不重复。子 Wiki 5 是**需求视角**（需要支持哪些平台、各平台差异），本文档是**实现视角**（代码怎么组织）|
