# 添加新的数据类型 Codec

## 角色
你是一个 Python 工程师，负责为 DSP 框架注册一种新数据类型的 Codec。

## 任务
给定已存在的 `DSPDtype`，把它的 Codec 注册到框架。

## 背景

Codec 的三个方法 **`to_double` / `from_double` / `fake_quantize`** 全部通过 golden C 的 convert 函数实现：

- **`from_double(t, dtype)`** — 量化：double → 原生 bits（如 bf16）
- **`to_double(raw, dtype)`** — 反量化：原生 bits → double
- **`fake_quantize(t, dtype)`** — 一次 round trip，截断到原生精度但保持 double 存储（内部已按 `subblock_size` 补零对齐，任意 shape 可用）

**DUT 类型统一复用 `_golden_codec` 这一个实例，不要继承子类。**

Real 类型（如 `double` 自身）用 `PassthroughCodec`（不过 C）。

注册位置：`src/dsp/core/dtype.py` 底部。

## 规则

1. MUST: DUT 类型注册 `_golden_codec` 实例
2. MUST: 调用 `register_codec(dtype, codec)`
3. NEVER: 继承 `GoldenCCodec` 子类
4. NEVER: 重写 `to_double / from_double / fake_quantize` —— 全走 golden C
5. NEVER: 写空子类（如 `class BF16Codec(GoldenCCodec): pass`）
6. 前提：对应的 `DSPDtype` 已定义，对应的 C convert 函数 `dsp_convert_{dtype}_double` / `dsp_convert_double_{dtype}` 已在 binding 中导出（`auto_register` 会自动挂到 manifest）

## 步骤

1. 确认 `src/dsp/core/dtype.py` 中已有目标 `DSPDtype`（没有先用 prompt 05 创建）
2. 在同文件底部 codec 注册区添加一行
3. 跑 `python -c "from dsp.core.dtype import get_codec, YOUR_DTYPE; print(get_codec(YOUR_DTYPE))"` 验证
4. `python -m pytest tests/ut -q`

## 输出格式

```python
# src/dsp/core/dtype.py 底部:
_golden_codec = GoldenCCodec()
register_codec(bf8,  _golden_codec)
register_codec(bf16, _golden_codec)
register_codec(my_new_dtype, _golden_codec)     # ← 新增
register_codec(double, PassthroughCodec())
```

## Examples

### Example 1（典型）: 注册 bf4 的 Codec

**前提:** `bf4 = DSPDtype(name="bf4", torch_dtype=torch.int8, subblock_size=32)` 已定义，C 侧有 `dsp_convert_bf4_double` 和 `dsp_convert_double_bf4`。

**代码:**
```python
# src/dsp/core/dtype.py 底部
register_codec(bf8,  _golden_codec)
register_codec(bf16, _golden_codec)
register_codec(bf4,  _golden_codec)   # ← 新增
register_codec(double, PassthroughCodec())
```

**Why:** 只需要一行 —— DUT 类型一律复用 `_golden_codec`，convert 函数名由 `auto_register.py` 从 binding 扫描自动注册到 `CONVERT` 表。

### Example 2（错误）: 创建空子类

```python
# WRONG
class BF4Codec(GoldenCCodec):
    pass

register_codec(bf4, BF4Codec())
```

**Fix:** 直接 `register_codec(bf4, _golden_codec)`。子类化没有任何意义，GoldenCCodec 已经根据传入的 `dtype.name` 查对应的 C 函数。

### Example 3（错误）: 手动实现转换

```python
# WRONG — 别用 torch 的原生转换，bf16 语义要过 C
class MyBF16Codec(GoldenCCodec):
    def from_double(self, t, dtype):
        return t.to(torch.bfloat16)     # ← 丢失的是 RNE 行为和硬件 bit 一致性
```

**Fix:** 一定要走 `_golden_codec`，让 C 侧的 `DoubleToBF16`（RNE 舍入）决定 bit 模式。

## 自检清单

- [ ] 一行 `register_codec(dtype, _golden_codec)`
- [ ] 没有新建 Codec 子类
- [ ] C 侧 `dsp_convert_double_{name}` / `dsp_convert_{name}_double` 已在 binding 中（`_raw_bindings.so`）
- [ ] `python -c "from dsp.core.dtype import get_codec; import dsp; get_codec(dsp.core.YOUR_DTYPE)"` 不报错
- [ ] `python -m pytest tests/ut -q` 全绿

## 边界情况

- golden C 不可用时 `to_double / from_double / fake_quantize` 会抛 `GoldenNotAvailable` —— 这是正确行为（用户需要先编译 `_raw_bindings.so`）
- 如果 DSPDtype 还不存在：先走 prompt 05 创建
- 如果 C convert 函数还没加：先走 prompt 03 把 binding 补上

---
[操作员：在此行下方提供新数据类型的 `name`（假设 `DSPDtype` 和 C binding 都已就位）。]
