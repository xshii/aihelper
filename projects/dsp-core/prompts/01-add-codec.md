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
1. 必须：继承 `GoldenCCodec`
2. 必须：在 `dtype=` 参数指定对应的 DSPDtype 实例
3. 禁止：实现 `_fallback_*` 方法（Python fallback 已删除，全走 golden C）
4. 禁止：手动调 `register_codec()`

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
