# 添加新的数据类型 Codec

## 角色
你是一个 Python 工程师，负责为 DSP 框架添加一种新的数据类型编解码器。

## 任务
给定一种数据类型名，创建一个 Codec 类，注册到框架。

## 背景
Codec 的三个方法（to_float / from_float / fake_quantize）**全部通过 golden C convert 函数实现**。
Python 层不需要知道定点格式的内部细节，全交给 C++。

新增 Codec 只需一行：

```python
class BFP16Codec(GoldenCCodec, dtype=bfp16):  # 定义即注册
    pass
```

`__init_subclass__` 自动注册，无需手动调 `register_codec()`。

## 规则
1. MUST: 继承 `GoldenCCodec`（不是 `TypeCodec`）
2. MUST: 在 `dtype=` 参数指定对应的 DSPDtype 实例
3. NEVER: 实现 `_fallback_*` 方法或重写 `to_float/from_float/fake_quantize`（Python fallback 已删除，全走 golden C）
4. NEVER: 手动调 `register_codec()`

## 步骤
1. 确认对应的 DSPDtype 已存在（如果没有，先用 prompt 05 创建）
2. 在 `src/dsp/core/codec.py` 底部添加一行 Codec 类
3. 在 `src/dsp/core/__init__.py` 中导出（如需要）

## 输出格式

```python
# 在 src/dsp/core/codec.py 底部添加:

class BFP16Codec(GoldenCCodec, dtype=_dtypes.bfp16):
    """bfp16 编解码器。定义即注册。"""
```

## Examples (样例)

完整样例见 `src/dsp/core/codec.py` 中 `IQ16Codec` 和 `IQ32Codec`。

### Example 1 (典型): 添加 bfp16 Codec

**任务:** 添加 bfp16 数据类型的 Codec。

**代码 diff:**

```diff
--- a/src/dsp/core/codec.py
+++ b/src/dsp/core/codec.py
@@ existing codecs
 class IQ16Codec(GoldenCCodec, dtype=_dtypes.iq16):
     """iq16 编解码器。定义即注册，全部委托给 golden C convert 函数。"""

 class IQ32Codec(GoldenCCodec, dtype=_dtypes.iq32):
     """iq32 编解码器。定义即注册，全部委托给 golden C convert 函数。"""
+
+class BFP16Codec(GoldenCCodec, dtype=_dtypes.bfp16):
+    """bfp16 编解码器。定义即注册，全部委托给 golden C convert 函数。"""
```

**验证命令:**

```bash
make test
```

**Why this output:**
- 继承 `GoldenCCodec`，三个方法（`to_float`/`from_float`/`fake_quantize`）全部由基类委托给 golden C，子类不需要实现任何方法。
- `dtype=_dtypes.bfp16` 通过 `__init_subclass__` 自动完成注册，无需手动调用。
- 只需在文件底部添加一行类定义，和 `IQ16Codec`/`IQ32Codec` 模式完全一致。

### Example 2 (错误): 继承了 TypeCodec 而不是 GoldenCCodec

**错误代码:**

```python
# WRONG — 继承了 TypeCodec
class BFP16Codec(TypeCodec, dtype=_dtypes.bfp16):
    """bfp16 编解码器。"""
```

**错误症状:**
- `TypeCodec` 是抽象基类，没有提供 `to_float`/`from_float`/`fake_quantize` 的实现。
- 调用时抛出 `TypeError: Can't instantiate abstract class BFP16Codec with abstract methods from_float, to_float`。
- 即使手动实现了这些方法，也违反了"全走 golden C"的设计：你写的 Python 实现不会和 golden C 对齐。

**正确做法:**

```python
# CORRECT — 继承 GoldenCCodec
class BFP16Codec(GoldenCCodec, dtype=_dtypes.bfp16):
    """bfp16 编解码器。定义即注册，全部委托给 golden C convert 函数。"""
```

## 自检清单
- [ ] 继承 `GoldenCCodec`（不是 `TypeCodec`）
- [ ] `dtype=` 指定了正确的 DSPDtype 实例
- [ ] 没有实现任何方法（全走 golden C）
- [ ] `make test` 通过

## 边界情况
- golden C 不可用时会抛 `GoldenNotAvailable`，这是正确行为
- 如果需要新的 DUT 类型，先在 `core/enums.py` 的 `DType.DUT` 加枚举值

---
[操作员：在此行下方提供新数据类型名。]
