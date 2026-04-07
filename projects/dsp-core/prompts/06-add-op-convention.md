# 添加算子调用约定（OpConvention）

## 角色
你是一个 Python 工程师，负责告诉框架一个新算子的 C 函数如何调用。

## 任务
当 C 函数的参数模式和已有的不同时，注册一个新的 OpConvention。

## 背景
OpConvention 声明两件事：
1. `output_shape(*inputs)` — 输出 shape 怎么从输入推算
2. `call_c_func(func, *inputs_np, **params)` — 怎么调 C 函数

用 `__init_subclass__` 自动注册：

```python
class FFTConvention(OpConvention, op="fft"):  # 定义即注册
    ...
```

## 已有 Convention

| Convention | 适用的 op | 参数模式 |
|-----------|-----------|---------|
| `UnaryConvention` | abs | func(x, out, count) |
| `ElementwiseConvention` | add, mul, sub | func(a, b, out, count) |
| `MatmulConvention` | matmul | func(A, B, C, M, K, N) |
| `LinearConvention` | linear | func(x, w, bias, out, scale, M, K, N) |
| `CorrelateConvention` | correlate | func(a, b, out, signal_len) |

**何时需要新 Convention？**
- 先看上表，如果新 op 的 C 函数参数模式和某个已有 Convention 一样 → 直接复用（在 `__init_subclass__` 的 `op=` 加名字即可）
- 如果参数个数、顺序或 reshape 逻辑不同 → 需要新建
- 如果不确定 → 先用已有 Convention 跑测试，如果报参数数量错误再新建

## 规则
1. MUST: 继承 `OpConvention`
2. MUST: 用 `op="name"` 或 `op=["name1","name2"]` 自动注册
3. MUST: `call_c_func` 用 `*inputs_np`（可变参数）
4. NEVER: 在 Convention 里调 quantize/dequantize（精度转换由 codec 层处理）
5. NEVER: 手动调 `register_convention()`

## 输出格式

```python
# 在 src/dsp/golden/op_convention.py 底部添加:

class FFTConvention(OpConvention, op="fft"):
    """FFT: 输入输出同 shape，C 函数: func(input, output, N)"""

    def output_shape(self, *inputs):
        return inputs[0].shape

    def call_c_func(self, func, *inputs_np, **params):
        x = inputs_np[0]
        N = x.shape[-1]
        out = np.zeros_like(x)
        func(x.flatten(), out.flatten(), N)
        return out
```

## Examples

### Example 1: 复用已有 Convention（新 op `dot_product`）

**场景：** 新增 `dot_product` 算子，C 函数签名为 `func(a, b, out, count)`，和 `ElementwiseConvention` 一样。

**做法：** 不需要新建 Convention，只需把 `dot_product` 加到已有的 `op=` 列表：

```python
# 修改前
class ElementwiseConvention(OpConvention, op=["add", "mul", "sub"]):
    def output_shape(self, *inputs):
        return inputs[0].shape

    def call_c_func(self, func, *inputs_np, **params):
        a, b = inputs_np[0].flatten(), inputs_np[1].flatten()
        out = np.zeros_like(a)
        func(a, b, out, len(a))
        return out

# 修改后（只改 op= 这一行）
class ElementwiseConvention(OpConvention, op=["add", "mul", "sub", "dot_product"]):
    ...  # 其余不变
```

**为什么不新建？** 参数模式完全一致：两个输入 flatten → 一个输出 → count。

### Example 2: 新建 Convention（新 op `fft`）

**场景：** 新增 `fft` 算子，C 函数签名为 `func(input, output, N)`，只有一个输入，且需要传 shape 维度 N。和已有 Convention 都不同。

**做法：** 新建 FFTConvention：

```python
class FFTConvention(OpConvention, op="fft"):
    """FFT: 输入输出同 shape，C 函数: func(input, output, N)"""

    def output_shape(self, *inputs):
        return inputs[0].shape

    def call_c_func(self, func, *inputs_np, **params):
        x = inputs_np[0]
        N = x.shape[-1]
        out = np.zeros_like(x)
        func(x.flatten(), out.flatten(), N)
        return out
```

**为什么不复用？** UnaryConvention 的签名是 `func(x, out, count)`，但 FFT 需要的 N 是最后一维的 shape 而不是元素总数 count，语义不同。

完整样例见 `src/dsp/golden/op_convention.py`。

## 自检清单
- [ ] `op="name"` 在类定义处（`__init_subclass__` 自动注册）
- [ ] `call_c_func` 用 `*inputs_np`
- [ ] `output_shape` 用 `*inputs`
- [ ] 没有 quantize/dequantize 调用
- [ ] `make test` 通过

## 边界情况
- 如果 output shape 依赖运行时参数（如 FFT 的 N）：在 call_c_func 中处理，output_shape 只负责静态推断
- 如果 C 函数返回多个输出：call_c_func 返回 tuple of ndarray，框架会自动拆分
- 如果参数数量报错（TypeError: func() takes N args）：说明 Convention 的 call_c_func 传参不对，检查 flatten/reshape
- 禁止在 Convention 里调 quantize/dequantize 的原因：精度转换由 codec 层统一处理，Convention 只管 numpy ↔ C 的桥接

---
[操作员：在此行下方提供新算子的 C 函数签名。]
