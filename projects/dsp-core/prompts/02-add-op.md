# 添加新的自定义算子

## 角色
你是一个 PyTorch 工程师，负责为 DSP 框架添加一个新的自定义算子。

## 任务
给定算子的数学公式，写一个 torch 实现并注册到框架。

## 背景

> **信息安全声明：** 由于信息安全要求，强 AI 无法知道具体硬件细节。当前代码为架构示例，所有类型名、函数名、精度参数均为示意。实际使用时需结合真实硬件规格进行适配。

只有 torch 没有的算子需要注册。注册后：

```python
result = dsp.ops.my_op(a, b)
```

框架自动处理伪量化、golden C 重定向、数据出数。你只需写纯 torch 实现。

## 规则
1. MUST: 用 `@register_op` 装饰器
2. MUST: 函数参数名有语义（出数时用参数名命名文件）
3. SHOULD: `golden_c={ComputeKey(...): "c_func_name"}` 映射 C 函数（有 C++ 实现时加）
4. SHOULD: `weight=Format.NN` 指定默认内存格式（有格式需求时加）
5. NEVER: 函数内部调 codec 或判断模式
6. 如果不确定 golden_c 怎么填：先不加，用纯 torch 跑通再迭代

## 步骤
1. 在 `src/dsp/ops/` 下创建新文件
2. 用 `@register_op` 装饰器注册
3. 在 `src/dsp/ops/__init__.py` 中 import 模块 + 加便捷函数

## 输出格式

```python
# src/dsp/ops/beamform.py

import torch
from . import register_op
from ..core.enums import DType, Format
from ..golden.manifest import ComputeKey

D, A = DType.DUT, DType.ACC

@register_op(
    # 默认格式（可选）
    weights=Format.NN,
    # golden C 映射（可选，没有 C++ 时不填）
    golden_c={
        ComputeKey(op="beamform", in0=D.IQ16, in1=D.IQ16, out0=D.IQ32,
                   acc=A.Q12_22, compute=D.IQ16):
            "sp_beamform_iq16_iq16_oiq32_acc_q12_22",
    },
)
def beamform(signal: torch.Tensor, weights: torch.Tensor) -> torch.Tensor:
    """波束成形: out[k] = sum_m(signal[m,k] * weights[m])"""
    return (signal * weights.unsqueeze(-1)).sum(dim=0)
```

在 `ops/__init__.py` 添加:
```python
from . import beamform as _beamform_mod  # noqa: F401

def beamform(signal, weights, **kwargs):
    return dispatch("beamform", signal, weights, **kwargs)
```

## 渐进式开发

```
阶段 1: @register_op 无参数 → 纯 torch，先跑通
阶段 2: 加 golden_c={...} → 接 C++ 实现
阶段 3: 加 format hints → 出数格式标注
阶段 4: 加 math_strategy → 数学验证（已知解 + 精确匹配）
```

不需要一步到位。

### math_strategy（阶段 4 — 最后适配）

> **信息安全声明：** 当前 math_strategy 实现为架构示例。实际使用时需结合真实硬件精度特性调整目标 pattern 和正则化参数。

math_strategy 为算子提供数学验证数据（已知解），在 generate_input 的 math 轮中自动替换 randn 输入。

**签名：**
```python
def _my_op_math(inputs, source_map):
    """
    inputs:     原始参数列表 [arg0, arg1, ...]
    source_map: 每个参数的来源 ["randn"|"op_output"|None, ...]
    
    返回: {arg_index: replacement_tensor} — 只替换 source=="randn" 的参数
          source=="op_output" 的参数来自上游算子，被动接受不替换
    """
```

**设计原则：**
1. 首算子（全 randn）：构造 near-diagonal 输入 + 设计权重使输出为 near-diagonal
2. 后续算子（部分 op_output）：被动接受上游输出，用 lstsq/ridge 设计权重回归目标 pattern
3. linear/matmul 天然承担回归职责 — 利用矩阵乘法把累积误差收回 near-diagonal
4. 如果不确定怎么写：先不加 math_strategy，op 会自动使用随机数据

**完整样例见 `src/dsp/ops/linear.py` 中 `_linear_math_strategy`。**

## 样例

### Example 1: 典型 — 有 golden_c（参考 `src/dsp/ops/linear.py`）

**算子文件 `src/dsp/ops/linear.py`：**
```python
@register_op(
    weight=Format.NN,
    golden_c={
        ComputeKey(op="linear", in0=D.IQ16, in1=D.IQ16, in2=D.IQ32, out0=D.IQ16,
                   acc=A.Q12_22, compute=D.IQ16): "sp_fused_linear_iq16_iq16_oiq16_acc_q12_22",
    },
)
def linear(input: torch.Tensor, weight: torch.Tensor, bias: torch.Tensor) -> torch.Tensor:
    return input @ weight + bias
```

**`ops/__init__.py` 中对应的便捷函数：**
```python
from . import linear as _linear_mod  # noqa: F401

def linear(input, weight, bias, **kwargs):
    return dispatch("linear", input, weight, bias, **kwargs)
```

**Why this output:**
- `golden_c` 指定了完整的 `ComputeKey`，因为已有 C++ 实现需要映射
- `weight=Format.NN` 指定了默认内存格式，因为 linear 的权重有格式需求
- 便捷函数的参数列表和算子函数签名一致（`input, weight, bias`）

### Example 2: 最简 — 无 golden_c（阶段 1 纯 torch）

**算子文件：**
```python
@register_op
def my_op(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    return a * b
```

**`ops/__init__.py` 中对应的便捷函数：**
```python
from . import my_op as _my_op_mod  # noqa: F401

def my_op(a, b, **kwargs):
    return dispatch("my_op", a, b, **kwargs)
```

**Why this output:**
- `@register_op` 不带参数（无括号），因为阶段 1 不需要 golden_c 和 format
- 后续有 C++ 实现时再按 Example 1 的模式补上 `golden_c`

## 自检清单
- [ ] `@register_op` 装饰（不是 `@op`）
- [ ] 函数签名接受 `torch.Tensor`
- [ ] 参数名有语义
- [ ] `ops/__init__.py` import + 便捷函数
- [ ] `make test` 通过

## 边界情况
- 如果不确定 ComputeKey 的 acc/compute 字段怎么填：先不加 golden_c，用阶段 1 纯 torch 跑通
- 如果 C 函数的参数模式和 linear/correlate 不同：需要先用 prompt 06 注册 OpConvention
- 如果函数名和已有 op 冲突：dispatch 会报 KeyError，改名即可

---
[操作员：在此行下方提供算子名称、数学公式、类型约束。]
