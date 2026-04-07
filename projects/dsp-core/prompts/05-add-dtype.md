# 定义新的 DSPDtype

## 角色
你是一个 Python 工程师，负责定义一种新的硬件数据类型。

## 任务
给定硬件规格，创建 DSPDtype + Codec + DType 枚举值。

## 背景
DSPDtype 只存最基本的元数据。DUT 格式的细节（frac_bits 等）由 golden C 处理，Python 不感知。

## 规则
1. 必须：填写 `name`, `torch_dtype`, `bits`, `is_complex`
2. 必须：`name` 全小写
3. 必须：同步在 `core/enums.py` 的 `DType.DUT` 加枚举值
4. 禁止：填 `frac_bits`、`qmin`、`qmax`（已移除，由 golden C 处理）

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

## 自检清单
- [ ] DSPDtype 字段：name, torch_dtype, bits, is_complex
- [ ] DType.DUT 枚举值和 DSPDtype.name 一致
- [ ] Codec 继承 GoldenCCodec（一行，无方法）
- [ ] `core/__init__.py` 导出
- [ ] `make test` 通过

---
[操作员：在此行下方提供硬件数据类型规格。]
