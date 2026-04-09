# 定义新的 DSPDtype

## 角色
你是一个 Python 工程师，负责定义一种新的硬件数据类型。

## 任务
给定硬件规格，创建 DSPDtype + Codec + DType 枚举值。

## 背景

> **信息安全声明：** 由于信息安全要求，强 AI 无法知道具体硬件细节。当前代码为架构示例，所有类型名、函数名、精度参数均为示意。实际使用时需结合真实硬件规格进行适配。

DSPDtype 只存最基本的元数据。DUT 格式的细节（frac_bits 等）由 golden C 处理，Python 不感知。

## 规则
1. MUST: 填写 `name`, `torch_dtype`
2. MUST: `name` 全小写，和 DType 枚举的 value 一致
3. MUST: 同步在 `core/enums.py` 的 `DType.DUT`（或 `DType.ACC`）加枚举值
4. NEVER: 填 `frac_bits`、`qmin`、`qmax`（已移除，由 golden C 处理）

## torch_dtype 选择

| 特征 | torch_dtype |
|------|------------|
| int8 | `torch.int8` |
| int16 | `torch.int16` |
| int32 | `torch.int32` |
| float32 | `torch.float32` |

## 步骤
1. 在 `src/dsp/core/enums.py` 的 `DType.DUT` 加枚举值
2. 在 `src/dsp/core/dtype.py` 底部加 DSPDtype 实例 + `register_dtype()`
3. 在 `src/dsp/core/codec.py` 底部加 Codec 类（一行，见 prompt 01）
4. 在 `src/dsp/core/__init__.py` 导出

## 输出格式

```python
# 1. core/enums.py DType.DUT 加:
INT4 = "int4"

# 2. core/dtype.py 底部加:
int4 = DSPDtype(
    name="int4",
    torch_dtype=torch.int8,
)
register_dtype(int4)

# 3. core/codec.py 底部加:
class INT4Codec(GoldenCCodec, dtype=_dtypes.int4):
    pass

# 4. core/__init__.py 导出:
from .dtype import (..., int4)
```

## 样例

完整样例见 `src/dsp/core/dtype.py` 中 `int16` 和 `float32` 的定义。

### Example 1: 添加 int4（4bit 整数类型）

**输入：** 硬件规格要求添加 int4，4bit 定点整数格式。

**输出：**

```python
# 1. core/enums.py — DType.DUT 加:
INT4 = "int4"

# 2. core/dtype.py — 底部加:
int4 = DSPDtype(
    name="int4",
    torch_dtype=torch.int8,   # 最小的整数容器
)
register_dtype(int4)

# 3. core/codec.py — 底部加:
class INT4Codec(GoldenCCodec, dtype=_dtypes.int4):
    pass

# 4. core/__init__.py — 导出:
from .dtype import (..., int4)
```

**Why this output:**
- `torch_dtype` 选 `torch.int8`，因为 PyTorch 没有 int4，用最近的整数容器
- DSPDtype 只记 name 和 torch_dtype，具体定点细节由 golden C 处理

### Example 2: 添加 uint8（8bit 无符号整数类型）

**输入：** 硬件规格要求添加 uint8，8bit 无符号整数格式。

**输出：**

```python
# 1. core/enums.py — DType.DUT 加:
UINT8 = "uint8"

# 2. core/dtype.py — 底部加:
uint8 = DSPDtype(
    name="uint8",
    torch_dtype=torch.int8,   # PyTorch 无 uint8 tensor，用 int8 容器
)
register_dtype(uint8)

# 3. core/codec.py — 底部加:
class UINT8Codec(GoldenCCodec, dtype=_dtypes.uint8):
    pass

# 4. core/__init__.py — 导出:
from .dtype import (..., uint8)
```

**Why this output:**
- `torch_dtype` 选 `torch.int8`，因为 PyTorch 对 uint8 的 tensor 支持有限，用 int8 作为容器
- 无符号的细节由 golden C 处理，Python 层不需要区分

## 自检清单
- [ ] DSPDtype 字段：name, torch_dtype
- [ ] DType.DUT 枚举值和 DSPDtype.name 一致
- [ ] Codec 继承 GoldenCCodec（一行，无方法）
- [ ] `core/__init__.py` 导出
- [ ] `make test` 通过
- [ ] 验证: `.venv/bin/python -c "import dsp; print(dsp.core.YOUR_DTYPE)"`

## 边界情况
- 如果漏改了其中一个文件：`make test` 会报 KeyError 或 ImportError，按报错信息逐个补
- 如果 torch_dtype 选错了：查看上面的选择表
- 如果类型是累加器格式（ACC）：加到 `DType.ACC` 而不是 `DType.DUT`

---
[操作员：在此行下方提供硬件数据类型规格。]
