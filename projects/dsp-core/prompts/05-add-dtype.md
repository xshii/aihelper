# 定义新的 DSPDtype

## 角色
你是一个 Python 工程师，负责定义一种新的硬件数据类型。

## 任务
给定硬件规格，创建 `DSPDtype` + 注册 Codec + 加 `DType` 枚举值。

## 背景

当前框架中已有的 DUT dtype：`bf8` / `bf16`，加上 real type `double`。

关键约定（**一定要理解**）：

1. **内存里所有 tensor 全程用 `torch.double` 存储。** `DSPDtype.torch_dtype` 只是个语义标签，**不是内存容器类型**。
2. **定点/低精度类型** 只在和 C / 硬件 DUT 文件交互时才真正变成原生 bit。
3. `subblock_size` = 128-bit 寄存器能装多少个该类型的元素（bf8=16, bf16=8, double=1）。**它不是 block 大小，只是 subblock/register 内的元素数**。

定义点：`src/dsp/core/dtype.py`。

## 规则

1. MUST: 填 `name`, `torch_dtype`, `subblock_size`
2. MUST: `name` 全小写，和 `DType.DUT`（或 `DType.REAL`）枚举 value 一致
3. MUST: 在 `DType.DUT` 或 `DType.REAL` 加对应枚举值
4. MUST: 加进 `_ALL_DTYPES` 字典
5. MUST: `register_codec(my_dtype, _golden_codec)`（DUT 类型）或 `PassthroughCodec()`（double 类）
6. MUST: 在 `src/dsp/core/__init__.py` re-export
7. NEVER: 把 `torch_dtype` 选成"容器位宽"—— 它是语义类型本身（如 bf16 → `torch.bfloat16`，不是 `torch.int16`）
8. NEVER: 在 DSPDtype 里塞 frac_bits / exponent_bias 等细节 —— 由 golden C 处理

## torch_dtype 选择

| 类型 | torch_dtype | subblock_size |
|---|---|---|
| bf16（brain float, 1+8+7） | `torch.bfloat16` | 8 |
| bf8（fp8 e4m3） | `torch.float8_e4m3fn` | 16 |
| double | `torch.double` | 1 |

新硬件类型如果 torch 没有原生支持，**先和操作员确认用什么容器**，不要自己拍脑袋。

## 步骤

1. 在 `DType.DUT`（或 `DType.REAL`）加枚举值
2. 加 `DSPDtype(...)` 实例
3. 加进 `_ALL_DTYPES`
4. 底部 `register_codec(...)`
5. 在 `src/dsp/core/__init__.py` re-export
6. 跑 `python -m pytest tests/ut -q`

## 输出格式

```python
# src/dsp/core/dtype.py

# 1. DType.DUT 加枚举值
class DUT(_StrEnum):
    BF8  = "bf8"
    BF16 = "bf16"
    BF4  = "bf4"        # ← 新增

# 2. 实例
bf4 = DSPDtype(name="bf4", torch_dtype=torch.int8, subblock_size=32)

# 3. 注册表
_ALL_DTYPES: dict[str, DSPDtype] = {d.name: d for d in [bf8, bf16, double, bf4]}

# 4. codec
register_codec(bf4, _golden_codec)
```

```python
# src/dsp/core/__init__.py
from .dtype import (
    DType,
    DSPDtype, bf8, bf16, double, bf4,   # ← 加 bf4
    ...
)
```

## Examples

### Example 1: 添加 bf4（4-bit 浮点）

**输入:** 硬件新增 `bf4`，4-bit 浮点（1+2+1），两元素一字节。

**修改:**
```python
# DType.DUT:
BF4 = "bf4"

# 实例 — torch 无原生 bf4，用 int8 作容器（两个 bf4 塞一个字节由 C 处理）
bf4 = DSPDtype(name="bf4", torch_dtype=torch.int8, subblock_size=32)

# register_codec(bf4, _golden_codec)
```

**Why:**
- torch 没有 bf4 → 和操作员确认后用 `torch.int8` 作容器（2 个 bf4 共享一字节，打包由 C 处理）
- 内存里 tensor 仍然是 `torch.double` 存储，`torch.int8` 这个 `torch_dtype` 标签只在写 DUT 文件 / 过 C 绑定时生效
- `subblock_size=32` 假设 128-bit 寄存器里装 32 个 4-bit 元素

### Example 2: 添加一个纯 real 类型 float32

**输入:** 需要一个 float32 作为中间精度类型。

**修改:**
```python
# DType.REAL:
FLOAT32 = "float32"

# 实例
float32 = DSPDtype(name="float32", torch_dtype=torch.float32, subblock_size=4)

# register_codec(float32, PassthroughCodec())    ← 不过 golden C
```

**Why:** 浮点原生类型，torch 直接支持，不需要通过 C convert。用 `PassthroughCodec` 直接复用 torch 的 `.float()`。

## 自检清单

- [ ] `DSPDtype` 三个必填字段齐全：`name`, `torch_dtype`, `subblock_size`
- [ ] 枚举值和 `DSPDtype.name` 字符串一致
- [ ] 加进 `_ALL_DTYPES`
- [ ] `register_codec(...)` 到位（DUT → GoldenCCodec；REAL → PassthroughCodec）
- [ ] `core/__init__.py` re-export
- [ ] 验证: `python -c "import dsp; print(dsp.core.bf4)"`（或对应名字）
- [ ] `python -m pytest tests/ut -q` 全绿

## 边界情况

- 如果是累加器类型（ACC，如 Q12_22）：加到 `DType.ACC`，**不要** 创建 DSPDtype 实例、**不要** 注册 codec，它只作为 ComputeKey 中的标签使用
- 如果 torch 没有对应的原生 dtype：用位宽匹配的容器（int8/int16），**但要和操作员确认命名和打包方式**
- 不要改 `subblock_size` 去"省内存" —— 这个值反映硬件寄存器布局

---
[操作员：在此行下方提供硬件数据类型规格（name, 位宽, torch 容器, subblock_size）。]
