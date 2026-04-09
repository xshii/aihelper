# dsp-core: 弱 AI 投喂手册

## 这是什么

> **信息安全声明：** 由于信息安全要求，强 AI 无法知道具体硬件细节。当前代码为架构示例，所有类型名、函数名、精度参数均为示意。实际使用时需结合真实硬件规格进行适配。

DSP 芯片验证框架。torch-like API，多模式验证（torch / pseudo_quant / golden_c）。

**当前状态：golden C 接口是 fake 的（纯 Python 模拟定点截断）。**
弱 AI 的核心任务：按 SDD（规格驱动开发）模式，逐步用真实 C++ 实现替换 fake 接口。

## 架构

```
src/dsp/
├── core/       类型系统（DSPDtype + DSPTensor + Enums）
├── golden/     C++ 封装（manifest 声明表 + fake_so 模拟 + pybind11 绑定）
├── data/       数据管线（DataPipe 链式 API + 工厂函数）
├── ops/        算子（@register_op + torch 实现 + golden_c 映射）
├── context/    上下文（模式切换 + 验证循环 + compute config）
└── config.py   全局配置
```

## SDD 开发流程

弱 AI 按以下顺序，每步有明确的验收标准：

### 阶段 1: 替换 fake golden C（优先级最高）

当前 `golden/fake_so/` 是 Python 模拟。硬件团队提供 `.h` + `.so` 后：

```
步骤 1: 运行 ./scripts/extract_golden.sh path/to/golden_release.rar（解压 .h + .so 到 golden_c/）
步骤 2: 用 prompt 03 在 manifest.py 注册 C 函数名
步骤 3: make build-golden 编译 pybind11 绑定
步骤 4: make test（真 .so 自动替换 fake_so）
步骤 5: make smoke — E2E 比数报告应显示 torch vs pseudo_quant 精度差异
```

验收：比数报告中 `max_diff > 0` 说明伪量化在工作。

### 阶段 2: 添加新算子

```
步骤 1: 用 prompt 02 写 torch 实现（@register_op，零配置即可运行）
步骤 2: 用 prompt 03 在 @register_op 的 golden_c 参数中添加 ComputeKey
步骤 3: 如果 C 函数参数模式不同，用 prompt 06 注册 OpConvention
步骤 4: 用 prompt 04 写测试
步骤 5: （最后适配）为算子添加 math_strategy — 见 prompt 02 "阶段 4" 说明
步骤 6: make ci
```

验收：`make ci` 全绿。

### 阶段 3: 添加新硬件类型

```
步骤 1: 用 prompt 05 在 core/dtype.py 定义 DSPDtype
步骤 2: 用 prompt 01 在 core/codec.py 添加 Codec（__init_subclass__ 自动注册）
步骤 3: 用 prompt 03 在 manifest 添加 CONVERT + COMPUTE 条目
步骤 4: 用 prompt 04 写测试
步骤 5: make ci
```

验收：`make ci` 全绿。

## Prompt 列表

| # | 文件 | 一句话 |
|---|------|--------|
| 01 | [01-add-codec.md](prompts/01-add-codec.md) | 添加 Codec（__init_subclass__ 自动注册，无 Python fallback） |
| 02 | [02-add-op.md](prompts/02-add-op.md) | 添加算子（@register_op + golden_c ComputeKey 映射） |
| 03 | [03-bridge-golden-c.md](prompts/03-bridge-golden-c.md) | 注册 C 函数到 manifest（ComputeKey 固定槽位 + DType 枚举） |
| 04 | [04-write-tests.md](prompts/04-write-tests.md) | 写测试（UT/IT/ST 分级，pytest markers） |
| 05 | [05-add-dtype.md](prompts/05-add-dtype.md) | 定义 DSPDtype（name + torch_dtype） |
| 06 | [06-add-op-convention.md](prompts/06-add-op-convention.md) | 注册 OpConvention（__init_subclass__ 自动注册） |

## 最简用法

```python
import dsp

def main():
    x = dsp.data.randn(4, 8, dtype=dsp.core.int16)
    w = dsp.data.randn(8, 4, dtype=dsp.core.int16)
    b = dsp.data.randn(1, 4, dtype=dsp.core.int16)
    return dsp.ops.linear(x, w, b)

dsp.context.run(main)
```

```bash
python my_test.py                      # 默认 generate_input（8 种策略含 math）
python my_test.py use_input            # 比数 → 终端摘要 + run_log.json + HTML 报告
```

## 比数报告

`use_input` 完成后自动生成三种输出：

| 输出 | 位置 | 说明 |
|------|------|------|
| 终端摘要 | stdout | PASS/WARN/FAIL + max_diff + cosine |
| run_log.json | case 目录内 | 机读，含所有轮次 + diff 统计 |
| compare_*.html | output 根目录 | 交互式 Plotly 报告，自动打开浏览器 |

HTML 报告结构（渐进式披露）：
1. **汇总表** — 默认展开，10 秒定性
2. **策略对比柱状图** — 默认展开，哪种数据模式误差最大
3. **详情（折叠）** — 点击展开，每个策略/输出文件：
   - 误差 CDF（"99% 元素误差 < 阈值？"）
   - Bland-Altman（"误差和信号幅度有关吗？"）
   - 信号+误差叠加（逐元素定位）

依赖: `pip install plotly`（可选，未安装时跳过 HTML 报告）

## 关键枚举

```python
from dsp.core.enums import DType, Mode, Format

DType.DUT.INT16        # 芯片原生定点
DType.REAL.FLOAT32    # 标准浮点
DType.ACC.Q12_22      # 累加器格式

Mode.TORCH            # 纯 torch
Mode.PSEUDO_QUANT     # 伪量化
Mode.GOLDEN_C         # C++ 实现

Format.ZZ             # Z 序分块
Format.NN             # 行优先分块
Format.ND             # 不分块
```

## 自定义异常

```python
from dsp.core.errors import (
    GoldenNotAvailable,    # golden C 未接入 → make build-golden
    ManifestNotFound,      # COMPUTE 表无匹配 → 在 @register_op golden_c 加 ComputeKey
    ConventionNotFound,    # 无 OpConvention → 在 op_convention.py 加类
    OpNotRegistered,       # 算子未注册 → 确认 @register_op 和 import
)
```
