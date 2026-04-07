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

如果新 op 的参数模式和上面都不同，需要新建。

## 规则
1. 必须：继承 `OpConvention`
2. 必须：用 `op="name"` 参数自动注册（不手动调 `register_convention()`）
3. 必须：`call_c_func` 用 `*inputs_np`（可变参数，不是固定 a, b）
4. 禁止：在 Convention 里调 quantize/dequantize

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

## 自检清单
- [ ] `op="name"` 在类定义处（`__init_subclass__` 自动注册）
- [ ] `call_c_func` 用 `*inputs_np`
- [ ] `output_shape` 用 `*inputs`
- [ ] 没有 quantize/dequantize 调用
- [ ] `make test` 通过

---
[操作员：在此行下方提供新算子的 C 函数签名。]
