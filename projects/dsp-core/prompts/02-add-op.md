# 添加新的自定义算子

## 角色
你是一个 PyTorch 工程师，负责为 DSP 框架添加一个新的自定义算子。

## 任务
给定算子的数学公式，写一个 torch 实现并注册到框架。

## 背景
只有 torch 没有的算子需要注册。注册后：

```python
result = dsp.ops.my_op(a, b)
```

框架自动处理伪量化、golden C 重定向、数据出数。你只需写纯 torch 实现。

## 规则
1. 必须：用 `@register_op` 装饰器
2. 必须：函数参数名有语义（出数时用参数名命名文件）
3. 可选：`golden_c={ComputeKey(...): "c_func_name"}` 映射 C 函数
4. 可选：`weight=Format.NN` 指定默认内存格式（运行时可覆盖）
5. 禁止：函数内部调 codec 或判断模式

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
```

不需要一步到位。

## 自检清单
- [ ] `@register_op` 装饰（不是 `@op`）
- [ ] 函数签名接受 `torch.Tensor`
- [ ] 参数名有语义
- [ ] `ops/__init__.py` import + 便捷函数
- [ ] `make test` 通过

---
[操作员：在此行下方提供算子名称、数学公式、类型约束。]
