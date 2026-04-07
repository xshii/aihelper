# 定义新的 DSPDtype

## 角色
你是一个 Python 工程师，负责定义一种新的硬件数据类型。

## 任务
给定硬件规格，创建 DSPDtype + Codec + DType 枚举值。

## 背景

> **信息安全声明：** 由于信息安全要求，强 AI 无法知道具体硬件细节。当前代码为架构示例，所有类型名、函数名、精度参数均为示意。实际使用时需结合真实硬件规格进行适配。

DSPDtype 只存最基本的元数据。DUT 格式的细节（frac_bits 等）由 golden C 处理，Python 不感知。

## 规则
1. MUST: 填写 `name`, `torch_dtype`, `bits`（`is_complex` 默认 False，复数类型必须设 True）
2. MUST: `name` 全小写，和 DType 枚举的 value 一致
3. MUST: 同步在 `core/enums.py` 的 `DType.DUT`（或 `DType.ACC`）加枚举值
4. NEVER: 填 `frac_bits`、`qmin`、`qmax`（已移除，由 golden C 处理）

## torch_dtype 选择

| 特征 | torch_dtype |
|------|------------|
| 实数 ≤ 32bit | `torch.float32` |
| 实数 > 32bit | `torch.float64` |
| 复数（IQ）≤ 32bit/分量 | `torch.complex64` |
| 复数 > 32bit/分量 | `torch.complex128` |

## 步骤
1. 在 `src/dsp/core/enums.py` 的 `DType.DUT` 加枚举值
2. 在 `src/dsp/core/dtype.py` 底部加 DSPDtype 实例 + `register_dtype()`
3. 在 `src/dsp/core/codec.py` 底部加 Codec 类（一行，见 prompt 01）
4. 在 `src/dsp/core/__init__.py` 导出

## 输出格式

```python
# 1. core/enums.py DType.DUT 加:
BFP16 = "bfp16"

# 2. core/dtype.py 底部加:
bfp16 = DSPDtype(
    name="bfp16",
    torch_dtype=torch.float32,
    bits=16,
)
register_dtype(bfp16)

# 3. core/codec.py 底部加:
class BFP16Codec(GoldenCCodec, dtype=_dtypes.bfp16):
    pass

# 4. core/__init__.py 导出:
from .dtype import (..., bfp16)
```

## 样例

完整样例见 `src/dsp/core/dtype.py` 中 `iq16` 和 `float32` 的定义。

### Example 1: 添加 bfp16（16bit 实数类型）

**输入：** 硬件规格要求添加 bfp16，16bit 块浮点实数格式。

**输出：**

```python
# 1. core/enums.py — DType.DUT 加:
BFP16 = "bfp16"

# 2. core/dtype.py — 底部加:
bfp16 = DSPDtype(
    name="bfp16",
    torch_dtype=torch.float32,   # 实数 ≤ 32bit → float32
    bits=16,
)
register_dtype(bfp16)

# 3. core/codec.py — 底部加:
class BFP16Codec(GoldenCCodec, dtype=_dtypes.bfp16):
    pass

# 4. core/__init__.py — 导出:
from .dtype import (..., bfp16)
```

**Why this output:**
- `is_complex` 省略，因为默认 False，bfp16 是实数类型
- `torch_dtype` 选 `torch.float32`，因为 16bit ≤ 32bit 实数

### Example 2: 添加 iq8（8bit IQ 复数类型）

**输入：** 硬件规格要求添加 iq8，8bit IQ 复数格式（I/Q 各 4bit）。

**输出：**

```python
# 1. core/enums.py — DType.DUT 加:
IQ8 = "iq8"

# 2. core/dtype.py — 底部加:
iq8 = DSPDtype(
    name="iq8",
    torch_dtype=torch.complex64,  # 复数 ≤ 32bit/分量 → complex64
    bits=8,
    is_complex=True,              # IQ 格式必须设 True
)
register_dtype(iq8)

# 3. core/codec.py — 底部加:
class IQ8Codec(GoldenCCodec, dtype=_dtypes.iq8):
    pass

# 4. core/__init__.py — 导出:
from .dtype import (..., iq8)
```

**Why this output:**
- `is_complex=True` 必须显式设置，否则默认 False 会导致 IQ 数据被当作实数处理
- `torch_dtype` 选 `torch.complex64` 而不是 `torch.float32`，因为 IQ 数据有虚部；用 float 会丢失虚部
- `bits=8` 是 I+Q 的总位宽，不是单分量位宽

## 自检清单
- [ ] DSPDtype 字段：name, torch_dtype, bits, is_complex
- [ ] DType.DUT 枚举值和 DSPDtype.name 一致
- [ ] Codec 继承 GoldenCCodec（一行，无方法）
- [ ] `core/__init__.py` 导出
- [ ] `make test` 通过

## 边界情况
- 如果漏改了其中一个文件：`make test` 会报 KeyError 或 ImportError，按报错信息逐个补
- 如果 torch_dtype 选错了：complex 类型必须用 torch.complex64/128，否则虚部会丢失
- 如果 bits 不确定：看硬件规格中的"word width"字段
- 如果类型是累加器格式（ACC）：加到 `DType.ACC` 而不是 `DType.DUT`

---
[操作员：在此行下方提供硬件数据类型规格。]
