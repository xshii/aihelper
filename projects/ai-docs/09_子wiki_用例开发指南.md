# 子 Wiki 9：用例开发指南

> 本篇是整个系列**对弱 AI 的核心产出**——"我要写一个新用例，具体怎么做"。
>
> 前面的 wiki 讲了框架、分层、pytest 能力，本篇把它们落成**可直接模仿的用例代码**。

---

## 目录

1. [用例的定位](#1-用例的定位)
2. [从需求到代码：一个完整走查](#2-从需求到代码一个完整走查)
3. [精度用例模板](#3-精度用例模板)
4. [性能用例模板](#4-性能用例模板)
5. [首用例怎么写](#5-首用例怎么写)
6. [跨平台 bit-exact 用例怎么写](#6-跨平台-bit-exact-用例怎么写)
7. [markers 使用规范](#7-markers-使用规范)
8. [parametrize：把启动矩阵展开成用例](#8-parametrize把启动矩阵展开成用例)
9. [fixture 使用模式](#9-fixture-使用模式)
10. [用例 review checklist](#10-用例-review-checklist)
11. [常见反模式](#11-常见反模式)

---

## 1. 用例的定位

**一个 pytest 用例 = 一次"在指定基线 + 指定执行矩阵下的裁决"**。它不是脚本，不是工具，是一次**可复现的业务裁决事件**。

一个合格的用例必须回答：

| 问题 | 回答方式 |
|---|---|
| 要验证什么？ | 函数名 + docstring |
| 在什么条件下验证？ | parametrize + markers（对应 00 · 4.4.4 启动矩阵）|
| 判定是什么？ | `assert verdict.is_pass()` —— bit 级 / 性能基线偏差 / DFX 联合 |
| 失败时给什么线索？ | compare 模块自动产出辅助分析报告（见 02 · 7.9）|

---

## 2. 从需求到代码：一个完整走查

### 需求（虚构）

> 新增一个精度用例：验证 **resnet50 在 proto_v1 + 全规格 + 普通功耗模式 + 初级业务软件版本** 下的功能正确性。用作 L1 基础回归。

### 步骤 1：识别用例维度（对应 00 · 4.4.4）

| 维度 | 取值 |
|---|---|
| 原型版本 | `proto_v1` |
| 运行模型 | `resnet50` |
| 运行规格 | `规格版本`（不是首用例，不是优化版本）|
| 比数模式 | 由框架决定（精度用例 → 首用例走 stage，后续走 end_to_end）|
| 阶段比数模式 | `初级`（业务软件版本）|
| 硬件规格 | `全规格` |
| 功耗模式 | `普通` |

### 步骤 2：决定命名（对应 00 · 5.2）

按命名规范 `{prototype_version}_{model_name}_{case_type}_{id}`：

```
proto_v1_resnet50_accuracy_001
```

### 步骤 3：决定 markers（对应 06 · 8.8 注册 + 8.7 strict）

```
@pytest.mark.accuracy          # 用例类型
@pytest.mark.l1                # 级别
@pytest.mark.cv                # 模型分类
@pytest.mark.resnet50          # 具体模型
@pytest.mark.spec_full         # 运行规格
```

### 步骤 4：写 pytest 函数

```python
# tests/accuracy/test_cv_resnet50.py
import pytest

@pytest.mark.accuracy
@pytest.mark.l1
@pytest.mark.cv
@pytest.mark.resnet50
@pytest.mark.spec_full
def test_resnet50_accuracy_001(fpga, case_loader):
    """resnet50 / 全规格 / 初级业务软件 / 普通功耗下的 bit 级精度验证。"""
    case = case_loader.load(
        case_id="proto_v1_resnet50_accuracy_001",
        model="resnet50",
        spec="spec_full",
        biz_sw_version="初级",
        hw_spec="全规格",
        power_mode="普通",
    )

    fpga.load_do(case.do)
    fpga.select_case(case)
    fpga.inject_stimulus(case.stimulus)
    fpga.trigger()
    fpga.wait_until_done(timeout_s=600)

    verdict = fpga.compare(case.golden)
    assert verdict.is_pass(), verdict.explain()
```

### 步骤 5：把用例加入套件（对应 02 · 3.4）

```yaml
# suites/cv_resnet50_accuracy.yaml
suite: cv_resnet50_accuracy
markers: [accuracy]
首用例: cv_resnet50_cpu_baseline   # 先跑首用例作为准入
业务软件版本: 初级
cases:
  - cv_resnet50_cpu_baseline      # 首用例
  - proto_v1_resnet50_accuracy_001  # 刚写的这个
```

### 步骤 6：本地跑一次确认

```bash
pytest tests/accuracy/test_cv_resnet50.py::test_resnet50_accuracy_001 -v
pytest -m "accuracy and l1 and resnet50" --html=r.html --self-contained-html
```

### 步骤 7：提 PR + review

按第 10 章 review checklist 自查，提 PR，触发 CI（PR 阶段跑 L0+L1）。

---

## 3. 精度用例模板

### 3.1 单条精度用例（最常见）

```python
import pytest

@pytest.mark.accuracy
@pytest.mark.l1
@pytest.mark.cv                     # 模型分类
@pytest.mark.resnet50               # 具体模型
@pytest.mark.spec_full              # 运行规格
def test_resnet50_fullspec_accuracy(fpga, case_loader):
    """resnet50 全规格精度 bit 级验证。"""
    case = case_loader.load("proto_v1_resnet50_accuracy_001")
    fpga.run(case)
    verdict = fpga.compare(case.golden)
    assert verdict.is_pass(), verdict.explain()
```

### 3.2 多阶段 dump 的精度用例（接入阶段性比数）

```python
@pytest.mark.accuracy
@pytest.mark.首用例                 # 触发框架的"首用例"策略：stage_compare + 通过后切 end_to_end
@pytest.mark.l1
def test_resnet50_cpu_baseline(fpga, case_loader):
    """首用例：CPU 简化实现，关闭所有硬件优化。"""
    case = case_loader.load(
        "cv_resnet50_cpu_baseline",
        execution_mode="cpu_simplified",   # 见 02 · 5.1
        stages=[
            {"name": "backbone_out", "end_layer": "layer4.2.relu"},
            {"name": "neck_out",     "end_layer": "fpn.out"},
            {"name": "head_out",     "end_layer": "classifier"},
        ],
    )
    fpga.run(case)

    # 阶段性比数：框架自动对每个 stage 做 bit 比对，产首发散阶段（02 · 7.12）
    verdict = fpga.compare_stages(case.golden_per_stage)
    assert verdict.is_pass(), verdict.explain()
```

### 3.3 批量精度用例（参数化）—— 避免复制粘贴

```python
CASES = [
    ("proto_v1_resnet50_accuracy_001", "resnet50",   "spec_full"),
    ("proto_v1_resnet50_accuracy_002", "resnet50",   "spec_mini"),
    ("proto_v1_bert_base_accuracy_001", "bert_base", "spec_full"),
]

@pytest.mark.accuracy
@pytest.mark.l1
@pytest.mark.parametrize(
    "case_id,model,spec",
    CASES,
    ids=lambda p: p[0],
)
def test_accuracy_suite(case_id, model, spec, fpga, case_loader):
    case = case_loader.load(case_id)
    fpga.run(case)
    verdict = fpga.compare(case.golden)
    assert verdict.is_pass(), verdict.explain()
```

---

## 4. 性能用例模板

性能用例默认走 **端到端比数**，通过解析 `[PERF]` 日志拿指标（03 · 3.1）。

```python
@pytest.mark.perf
@pytest.mark.l2
@pytest.mark.parametrize("batch_size", [1, 8, 32])
def test_resnet50_perf(batch_size, emu, case_loader, perf_baseline):
    """resnet50 性能在 emu（性能权威出口，见 03 · 3.6）上的回归。"""
    case = case_loader.load(
        f"proto_v1_resnet50_perf_bs{batch_size}",
        execution_mode="hw_optimized",   # 开满硬件优化
    )
    emu.run(case, rounds=5, warmup=1)

    metrics = emu.parse_perf_log(case)        # 解析 [PERF] 日志（03 · 3.1）
    verdict = perf_baseline.judge(case, metrics)

    assert verdict.is_pass_or_warn(), verdict.explain()
    # 注：性能用例允许 WARN，不会单纯因性能小幅偏差 FAIL 整个回归
```

### 4.1 关键差异

| 维度 | 精度用例 | 性能用例 |
|---|---|---|
| 默认平台 | fpga（功能主力）| **emu**（性能权威）|
| 默认比数模式 | end_to_end；首用例走 stage | end_to_end（见 03 · 3） |
| 采样次数 | 1 次 | N=5 取中位数，首次 warmup 不计 |
| 裁决 | PASS / FAIL（bit 级）| PASS / WARN / FAIL（基线偏差阈值）|
| 失败后自动回落 | 无（bit 就是 bit）| 有（回落到阶段性比数定位，见 02 · 3.2）|

---

## 5. 首用例怎么写

完整代码示例见 § 3.2 多阶段 dump 的精度用例。关键约束：

- **每个精度用例集必须至少有 1 个首用例**（02 · 5.3），打 `@pytest.mark.首用例` + `@pytest.mark.l0`
- `execution_mode="cpu_simplified"`（隐含 hw_optimizations=disabled + 不看端到端时延）
- 首用例跑通后，框架自动把套件内后续用例的比数模式切为 `end_to_end`（02 · 5.5）

> 首用例本质 = "CPU 简化 + 关闭所有硬件优化"的参照版本（见 02 · 5.1）。

---

## 6. 跨平台 bit-exact 用例怎么写

需求：同一用例在 fpga / link / rtl2c / emu 上输出必须完全一致（05 · FR-3）。

**一行实现**——用参数化 fixture（06 · 8.5）：

```python
@pytest.fixture(params=["fpga", "link", "rtl2c", "emu"])
def platform(request):
    return ADAPTERS[request.param]()   # adapter 自动加载（见 06 · 5）

@pytest.mark.bit_exact
@pytest.mark.l1
def test_cross_platform_bit_exact(platform, case_loader):
    """同一用例跨 4 个可执行平台的 bit 级一致性校验。"""
    case = case_loader.load("proto_v1_resnet50_accuracy_001")
    platform.run(case)
    verdict = platform.compare(case.golden)
    assert verdict.is_pass(), f"{platform.name}: {verdict.explain()}"
```

pytest 自动展开成 4 个用例：
```
test_cross_platform_bit_exact[fpga]
test_cross_platform_bit_exact[link]
test_cross_platform_bit_exact[rtl2c]
test_cross_platform_bit_exact[emu]
```

---

## 7. markers 使用规范

### 7.1 marker 速查

| 类别 | 取值 | 必加? |
|---|---|---|
| 用例类型 | `accuracy` / `perf` / `functional` / `stability` | ✅ 四选一 |
| 级别 | `l0` / `l1` / `l2` / `l3` | ✅ 四选一 |
| 模型分类 | `cv` / `nlp` / `mm` | ✅ 三选一 |
| 首用例 | `首用例` | 按需 |
| 跨平台一致 | `bit_exact` | 按需 |
| 平台约束 | `fpga_only` / `emu_only` | 按需 |
| 具体模型 | `resnet50` / `bert_base` / ... | 按需 |
| 运行规格 | `spec_mini` / `spec_full` | 按需 |

### 7.2 命令行筛选

```bash
pytest -m "accuracy and l0"                    # L0 精度
pytest -m "perf and resnet50 and not fpga_only" # 所有非 FPGA 专属的 resnet50 性能
pytest -m "l1 and (cv or nlp)"                  # L1 的 CV 或 NLP
```

### 7.3 注册（conftest.py，见 06 · 8.8）

**所有 marker 必须在 conftest.py 注册**，配合 `pytest --strict-markers` 防拼写错。

---

## 8. parametrize：把启动矩阵展开成用例

00 · 4.4.4 启动矩阵的每一行自然对应一个 parametrize 组合：

```python
# 启动矩阵组合
MATRIX = [
    # (原型版本, 模型, 运行规格, 阶段比数模式, 硬件规格, 功耗)
    ("proto_v1", "resnet50",  "spec_full", "初级", "全规格",  "普通"),
    ("proto_v1", "resnet50",  "spec_full", "进阶", "全规格",  "普通"),
    ("proto_v1", "resnet50",  "spec_mini", "初级", "少核",   "低功耗"),
    ("proto_v2", "bert_base", "spec_full", "初级", "跨 DIE", "普通"),
]

@pytest.mark.accuracy
@pytest.mark.l2
@pytest.mark.parametrize(
    "proto,model,spec,biz_ver,hw,power",
    MATRIX,
    ids=lambda row: "_".join(str(x) for x in row),   # 生成可读用例名
)
def test_accuracy_matrix(proto, model, spec, biz_ver, hw, power, fpga, case_loader):
    case = case_loader.load_matrix_case(proto, model, spec, biz_ver, hw, power)
    fpga.run(case)
    assert fpga.compare(case.golden).is_pass()
```

**优势：**
- 矩阵集中在一处，不靠复制粘贴
- 用例名自动可读：`test_accuracy_matrix[proto_v1_resnet50_spec_full_初级_全规格_普通]`
- 加一行矩阵 = 多一个用例，不改函数

---

## 9. fixture 使用模式

### 9.1 标准 fixture 清单（由 conftest 提供）

| fixture | scope | 用途 |
|---|---|---|
| `baseline` | session | 当前 `baseline_id` / `rtl_commit` / `gc_version` |
| `cmc_client` | session | CMC 制品仓客户端 |
| `fpga` | module | FPGA adapter 实例（自动加载当前基线）|
| `link` / `rtl2c` / `emu` | module | 其他平台 adapter |
| `case_loader` | module | 用例 + GOLDEN 加载器 |
| `perf_baseline` | session | 性能基线（见 03 · 3.2）|
| `tmp_path` | function | pytest 自带，每用例的临时目录 |
| `caplog` | function | pytest 自带，日志断言 |

### 9.2 自定义 fixture 的时机

**抽 fixture 的红线：**

- **单个用例用不到** → 不抽
- **2 个用例用到** → 局部抽（同文件或 `tests/<category>/conftest.py`）
- **3+ 用例或跨目录用到** → 上抽到全局 conftest

### 9.3 示例：自定义 golden_pair fixture

```python
# tests/accuracy/conftest.py
@pytest.fixture
def golden_pair(baseline, case_loader):
    """提供 (case, golden) 对，自动套用当前基线的 gc_version。"""
    def _load(case_id: str):
        case = case_loader.load(case_id)
        golden = case_loader.load_golden(case_id, gc_version=baseline.gc_version)
        return case, golden
    return _load

def test_with_pair(fpga, golden_pair):
    case, golden = golden_pair("proto_v1_resnet50_accuracy_001")
    fpga.run(case)
    assert fpga.compare(golden).is_pass()
```

---

## 10. 用例 review checklist

### 10.1 必须满足

- [ ] 函数名清晰表达"验证什么"
- [ ] docstring 一句话说明场景
- [ ] markers 至少有：用例类型 + 级别 + 模型分类
- [ ] 所有 markers 都已在 conftest 注册
- [ ] 用例 ID 符合 00 · 5.2 命名规范
- [ ] 裁决是 `assert verdict.is_pass()` 且带 `verdict.explain()` 作为错误消息
- [ ] 函数 < 50 行；超了拆 helper 或 fixture
- [ ] 类型标注完整（pytest 用例的参数一般是 fixture，类型由 fixture 签名决定；自定义参数化用 `parametrize` 类型标注）
- [ ] 用例可以独立跑（不依赖其他用例的执行顺序）
- [ ] 精度用例：对应套件里至少有 1 个首用例

### 10.2 建议

- [ ] 用 `parametrize` 代替复制粘贴
- [ ] 超时用 `@pytest.mark.timeout` / `@stage_timeout` 显式声明
- [ ] 参数化的 `ids=` 让用例名可读
- [ ] 资源准备用 fixture，不在用例函数里起进程 / 连板

### 10.3 红线（出现就拒绝 merge）

- [ ] 硬编码路径（要用 fixture 或 `tmp_path`）
- [ ] 魔法字符串（要用枚举）
- [ ] 用例里手写 if-else 平台判断（破坏了分层，要挪到 adapter）
- [ ] 用例里自定义容忍度（精度裁决只有 bit 级一个标准）
- [ ] 改了核心领域 / 能力服务代码（应该在专门 PR 里做，见 06 · 5.3 禁止）

---

## 11. 常见反模式

### 11.1 ❌ 为了"复用"滥抽 helper

3 个几乎一样的用例（`test_a` / `test_b` / `test_c` 都调用 `_load_and_run(case_id)`）应该用 `parametrize` 展开成一个用例 + 数据列表，不是抽 helper。详见 § 8。

### 11.2 ❌ 在用例里写 if-else 平台分支

```python
# Bad
def test_something(platform_name):
    if platform_name == "fpga":
        adapter = FpgaAdapter()
        adapter.do_fpga_thing()
    elif platform_name == "emu":
        adapter = EmuAdapter()
        adapter.do_emu_thing()
    # ...
```

**问题**：分层被打穿，用例感知了平台细节。

```python
# Good
@pytest.fixture(params=["fpga", "emu"])
def platform(request):
    return ADAPTERS[request.param]()

def test_something(platform):
    platform.do_thing()   # 统一接口
```

### 11.3 ❌ 自定义容忍度

```python
# Bad
def test_accuracy(fpga):
    actual = fpga.run(case)
    assert cosine_similarity(actual, golden) > 0.999  # 自己发明的容忍度
```

**问题**：精度裁决只有一个标准——bit 级一致。任何自定义阈值都是绕过体系。

```python
# Good
def test_accuracy(fpga):
    fpga.run(case)
    verdict = fpga.compare(case.golden)   # 框架内 bit 级 + 辅助分析
    assert verdict.is_pass(), verdict.explain()
```

### 11.4 ❌ 用例之间隐式依赖执行顺序

```python
# Bad
_shared_state = {}

def test_load():
    _shared_state["do"] = load_do()   # 依赖它先跑

def test_run():
    run(_shared_state["do"])          # 挂了不知道是 load 出问题还是 run
```

**问题**：单跑 `test_run` 会 NameError；xdist 并行时更乱。

```python
# Good
@pytest.fixture(scope="module")
def do_handle():
    return load_do()

def test_run(do_handle):
    run(do_handle)
```

### 11.5 ❌ 在用例函数里起 / 关资源

用例函数里 `Popen` + `try/finally terminate` → 失败时易泄漏 + 多个用例重复同一段代码。资源生命周期统一交给 `@pytest.fixture` 的 `yield` 写法管理（详见 § 9）。

### 11.6 ❌ 长用例不拆阶段

```python
# Bad
def test_everything(fpga):
    # 200 行：加载 + 配置 + 注入 + 触发 + 比对 + 归档
```

**问题**：失败时不知道哪一步；函数长度违反 < 50 行约定。

```python
# Good：把步骤抽成 adapter 方法或 helper（动作函数）
def test_accuracy(fpga, case_loader):
    case = case_loader.load(...)
    fpga.run(case)                         # adapter 内部封装了加载/配置/注入/触发
    assert fpga.compare(case.golden).is_pass()
```

### 11.7 ❌ 静默失败

`try: ... except Exception: pass` 吞掉异常 → 调试地狱。让异常自然抛出；必须 catch 时显式处理并保留信息（`result.explain()`）。
```

---

## 附：新增用例的一页 checklist

1. **识别维度**：原型版本 / 模型 / 规格 / 阶段比数模式 / 硬件规格 / 功耗模式
2. **定用例 ID**：按 00 · 5.2 命名规范
3. **定 markers**：至少三个（类型 / 级别 / 模型分类）
4. **写 pytest 函数**：用现有 fixture，bit 级裁决
5. **加到套件 yaml**：确保套件有首用例
6. **本地跑通**：`pytest <path> -v`
7. **对照第 10 章 checklist 自查**
8. **提 PR**
