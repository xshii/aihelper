# 添加新的自定义算子

## 角色
你是一个 PyTorch 工程师，负责为 DSP 框架添加一个新算子。

## 任务
给定算子的数学定义，在 `src/dsp/ops/<op>/__init__.py` 中完成 torch 参考实现 + C 调用约定 + （可选）math strategy 的全部注册。

## 背景

> **信息安全声明：** 强 AI 无法看到具体硬件细节。本 prompt 中所有类型名、函数名、C 绑定函数名均为示意，实际使用时以操作员提供的硬件手册为准。

**一个 op = 一个子目录**（不是单文件）：

```
src/dsp/ops/linear/
├── __init__.py      ← Python: @register_op 函数 + OpConvention 子类 + math_strategy
├── dsp_matrix.h     ← C++: dsp_{op}_{dut} 模板特化（调 golden 硬件接口）
└── bind.cpp         ← pybind11: 把模板暴露给 Python
```

**三条自动化机制（弱 AI 需要理解，但不需要手动触发）：**

1. **`ops/__init__.py::_auto_import_ops`** 会扫描 `ops/` 下所有子目录并 import —— 新 op 不需要手改任何 `__init__.py` import 语句。只要文件在，装饰器就会跑。
2. **`golden/auto_register.py`** 扫描 `_raw_bindings.so` 里所有 `dsp_*` 函数，自动填 `manifest.COMPUTE` / `manifest.CONVERT`。`@register_op` **不需要** `golden_c=` 参数。
3. **Pylance 类型提示** 通过 `src/dsp/ops/__init__.pyi` 声明 —— 新 op 如果希望 IDE 自动补全，加一行 stub 即可。

**@register_op 的可选参数：**
```python
@register_op(
    weight=Format.NN,              # 参数名到默认 Format 的 kwarg（可省）
    math_strategy=_my_math_fn,     # 数学验证策略（可省）
)
```
**没有 `golden_c` 参数**。

## 规则

1. MUST: 在 `src/dsp/ops/<op>/__init__.py` 定义算子（目录名 = op 名）
2. MUST: `@register_op` 装饰纯 torch 参考实现，参数名有语义
3. MUST: 如果要过 golden_c，额外定义一个 `OpConvention` 子类（见 prompt 06）
4. SHOULD: 参数用 Format 提示（例如 `weight=Format.NN`）
5. NEVER: 函数内部判断 mode / 直接调 codec / 直接调 golden
6. NEVER: 在 `ops/__init__.py` 里加手动 import —— `_auto_import_ops` 会扫
7. NEVER: 传 `golden_c={...}` 给装饰器（老 API 已废弃）

## 步骤

1. 在 `src/dsp/ops/<op>/` 建目录 + 空文件 `__init__.py`
2. 在 `__init__.py` 写：
   - 如果有 C 绑定：`class <Op>Convention(OpConvention, op="<op>")` + `call_c_func`
   - `@register_op(...)` 装饰的纯 torch 函数
   - （可选）`_<op>_math_strategy(inputs, source_map) -> (replacements, expected)`
3. 如果有 C 实现：按 prompt 03 加 `dsp_*.h` + `bind.cpp`
4. 在 `src/dsp/ops/__init__.pyi` 加一行 stub（可选，让 Pylance 认识）
5. 验证：
   - `python -c "import dsp; print('my_op' in dsp.ops.list_ops())"`
   - `python -m pytest tests/ut/ops -q`

## 渐进式四阶段

```
阶段 1: 纯 torch             →  @register_op + torch 函数
阶段 2: 加格式提示           →  @register_op(input=Format.ZZ, weight=Format.NN)
阶段 3: 接 golden C          →  加 dsp_*.h + bind.cpp + OpConvention 子类（自动注册到 manifest）
阶段 4: 加 math strategy     →  @register_op(math_strategy=fn) + 数学可验证的已知解
```

## 输出格式

### 阶段 1/2 模板（纯 torch + 格式提示）

```python
# src/dsp/ops/my_op/__init__.py
"""my_op: 简述算子语义。"""

from __future__ import annotations

import torch

from .. import register_op
from ...core.enums import Format


@register_op(weight=Format.NN)
def my_op(x: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    """out = x @ weight"""
    return x @ weight
```

### 阶段 3 模板（有 golden_c）

```python
# src/dsp/ops/my_op/__init__.py
"""my_op torch 实现 + C 调用约定 集中在一个文件。"""

import numpy as np
import torch

from .. import register_op
from ...core.enums import Format
from ...core.convention import OpConvention
from ...core.block import pad_to_block, pad_dim, get_block_shape


class MyOpConvention(OpConvention, op="my_op"):
    """func(dst, src0, src1, M, K, N) — ZZ × NN → ZZ 的矩阵布局。"""

    def output_shape(self, *inputs):
        return (*inputs[0].shape[:-1], inputs[1].shape[-1])

    def call_c_func(self, func, *inputs_np, **params):
        key = params.get("compute_key")
        dtype_name = str(key.src0) if key else "bf16"
        # ... pad / flatten / 调 func / reshape / crop
        ...


@register_op(weight=Format.NN)
def my_op(x: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    return x @ weight
```

### Pylance stub（可选，`src/dsp/ops/__init__.pyi`）

```python
def my_op(x: torch.Tensor, weight: torch.Tensor,
          *, compute: str | None = None, output_dtype: str | None = None) -> torch.Tensor: ...
```

## Examples

### Example 1（参考）: `src/dsp/ops/linear/__init__.py`

最完整的参考，含四阶段全部特性：
- `LinearConvention(OpConvention, op="linear")` 里处理 batch/pad/flatten
- `@register_op(weight=Format.NN, math_strategy=_linear_math_strategy)`
- 纯 torch fallback：`torch.matmul(x, weight) + bias`

读代码时重点看：
- 顶部的 `_prepare_2d` 辅助函数：怎么 pad 和转行/列优先
- `LinearConvention.call_c_func`：按 batch 循环的骨架
- `_linear_math_strategy`：用 lstsq 构造已知解

### Example 2（最简）: 阶段 1 纯 torch

```python
# src/dsp/ops/gelu/__init__.py
import torch
from .. import register_op

@register_op
def gelu(x: torch.Tensor) -> torch.Tensor:
    return torch.nn.functional.gelu(x)
```

**Why:**
- 没有 C 实现 → 不写 `OpConvention`，golden_c 模式自动 fallback 到 torch
- 没有格式需求 → 装饰器无参数
- 新加的目录/文件会被 `_auto_import_ops` 扫到

### Example 3（阶段 4）: math_strategy 的签名

```python
def _my_math_strategy(inputs: list, source_map: list) -> tuple[dict, torch.Tensor]:
    """
    inputs:     原始参数列表
    source_map: 每个参数的来源 [TensorSource.RANDN | OP_OUTPUT | None, ...]
    返回:        (replacements={arg_idx: new_tensor}, expected=目标 tensor)
                 只替换 source=RANDN 的参数；source=OP_OUTPUT 是上游结果，被动接受
    """
    ...
```

详细示例见 `src/dsp/ops/linear/__init__.py` 里的 `_linear_math_strategy`。

## 自检清单

- [ ] `src/dsp/ops/<op>/__init__.py` 存在
- [ ] 用 `@register_op`（不是 `@op`）
- [ ] 参数名有语义（会用作保存的文件名）
- [ ] 没有在装饰器里写 `golden_c={...}`
- [ ] 没有手动改 `ops/__init__.py`
- [ ] 如果有 C 绑定：`OpConvention` 子类有 `op=` 参数自动注册
- [ ] `python -c "import dsp; print('my_op' in dsp.ops.list_ops())"` 为 True
- [ ] `python -m pytest tests/ut/ops -q` 全绿

## 边界情况

- 纯 torch 没有 C 实现时：`dispatch_golden_c` 会返回 None，自动降级到 torch —— 预期行为
- 函数名和已有 op 冲突：`dispatch` 会报错，改名即可
- 装饰器找不到合适的 `ComputeKey`：先跑阶段 1 纯 torch 验证接入，再加 C 实现
- 参数名用作磁盘文件名 —— 不要取 `a, b, c` 这种 —— 用 `input, weight, bias` 这类

---
[操作员：在此行下方提供算子名、数学定义、类型约束。]
