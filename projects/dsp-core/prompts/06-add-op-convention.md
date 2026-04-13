# 添加算子调用约定（OpConvention）

## 角色
你是一个 Python 工程师，负责告诉框架一个新算子的 C 函数该怎么调。

## 任务
当新算子的 C 签名和已有算子不一样时，在 op 所在目录的 `__init__.py` 里定义一个 `OpConvention` 子类。

## 背景

Golden C dispatch 的流程：

```
dsp.ops.<op>(args)
 → wrapper 检查 mode
 → mode=golden_c 时 dispatch_golden_c(op_name, args, ...)
 → require_convention(op_name).call_c_func(func, *args_np, compute_key=...)
 → convention 负责：pad / 分型 / flatten → 调 func → reshape / unpad → 返回 numpy
```

**所有 tensor 在进入 convention 前已经是 double numpy，出去后也是 double numpy。** DUT bit 转换（double ↔ bf16/bf8）由 C++ binding 层的 `to_dut<DUT>` / `from_dut` 自动完成 —— **convention 不用管类型转换**。

convention 负责的是：
1. 形状准备（pad 到 block 对齐）
2. 格式排列（ZZ row-major flat / NN col-major flat / ND）
3. 输出裁剪（从 padded 切回 orig shape）
4. batch 循环（如果 C 函数只处理单个 2D）

## 已有 Convention

| 类 | op | C 签名 | 格式 |
|---|---|---|---|
| `MatmulConvention` | `matmul` | `func(dst, input_zz, weight_nn, M, K, N)` | ZZ × NN → ZZ |
| `LinearConvention` | `linear` | `func(dst, input_zz, weight_nn, bias, scale_exp, M, K, N)` | ZZ × NN + ND → ZZ |
| `LayernormConvention` | `layernorm` | `func(dst, src, gamma, beta, N)` | ND |
| `TransposeConvention` | `transpose` | 纯 Python unblock → transpose → re-block（无 C 函数） | ZZ → ZZ |

**何时需要新 Convention？**
- C 函数参数个数/顺序/格式组合任一处不同 → 新建
- 只是 dtype 组合变化 → **不需要新 Convention**（prompt 03 加 bind 就够）

## 注册机制

```python
class MyConvention(OpConvention, op="my_op"):
    ...
```

`__init_subclass__` 读取 `op=` 参数，创建实例并注册到 `_CONVENTIONS[op_name]`。**不要** 手动 `register_convention(...)`。`op=` 也可以传 list 给多个 op 共享同一个 convention。

## 常用工具（`src/dsp/core/block.py`）

| 函数 | 用途 |
|---|---|
| `get_block_shape(dtype_name, fmt) -> (bh, bw)` | 查 (dtype, format) 的 block 高/宽 |
| `pad_dim(dim, block) -> int` | 向上对齐到 block 的倍数 |
| `pad_to_block(t, dtype_name, fmt) -> Tensor` | 2D tensor 整体 pad（后两维） |
| `to_block / from_block` | ND ↔ 分块 ZZ/NN |
| `format_to_dut / format_from_dut` | numpy 版本的 pad + 分块（给 convention 直接用） |

## 规则

1. DO: 变量名用 `dst, src0, src1, src2` 和 C 对齐
2. DO: `dst` 作为 `func` 的第一个参数
3. DO: 矩阵类复用 `core.block` 里的 `pad_to_block / pad_dim / get_block_shape`
4. DO: batch 维度由 convention 自己循环处理（C 函数只看 2D）
5. DON'T: 在 convention 里做 `double → bf16` 转换 —— binding 层做
6. DON'T: 和 `_CONVENTIONS` 字典直接交互（靠 `__init_subclass__`）

## 步骤

1. 找到 op 的 `src/dsp/ops/<op>/__init__.py`
2. 定义 `class <Op>Convention(OpConvention, op="<op>")`
3. 实现两个方法：
   - `output_shape(*inputs)` — 返回输出 shape（支持任意 batch）
   - `call_c_func(func, *inputs_np, **params)` — pad / flatten / 调 func / reshape / crop
4. `params` 里常用的：
   - `compute_key: ComputeKey` — 含 `src0/src1/dst0/compute_dtype` 等字符串，用来查 `dtype_name` 和 block shape
5. `python -c "from dsp.core.convention import _CONVENTIONS; print(_CONVENTIONS)"` 验证注册
6. `python -m pytest tests/ut/ops -q`

## 模板

### 模板 A: elementwise（ND，无分型）

```python
class MyElemConvention(OpConvention, op="my_elem"):
    """func(dst, src0, src1, N)"""

    def output_shape(self, *inputs):
        return inputs[0].shape

    def call_c_func(self, func, *inputs_np, **params):
        src0 = inputs_np[0].flatten().astype(np.double)
        src1 = inputs_np[1].flatten().astype(np.double)
        dst = np.zeros(src0.size, dtype=np.double)
        func(dst, src0, src1, src0.size)
        return dst.reshape(inputs_np[0].shape)
```

### 模板 B: 矩阵（ZZ × NN → ZZ，含 batch 循环）

参考 `src/dsp/ops/linear/__init__.py` 里 `MatmulConvention` 和 `LinearConvention` —— 这是最完整的模板，照抄即可。

关键点：
```python
def call_c_func(self, func, *inputs_np, **params):
    key = params.get("compute_key")
    dtype_name = str(key.src0) if key else "bf16"

    # batch 循环：C 只处理单个 2D
    batch_shape, src0_list = _to_2d_batches(inputs_np[0])
    _, src1_list = _to_2d_batches(inputs_np[1])

    results = []
    for s0, s1 in zip(src0_list, src1_list):
        # 1. pad 到 block 对齐
        #    bf16 ZZ block=(16,16), NN block=(16,32)
        input_flat, weight_flat, M, K, N, orig_M, orig_N = \
            _prepare_2d(s0, s1, dtype_name)

        # 2. 分配输出
        dst_flat = np.zeros(M * N, dtype=np.double)

        # 3. 调 C 函数
        func(dst_flat, input_flat, weight_flat, M, K, N)

        # 4. reshape + crop 回原 shape
        results.append(dst_flat.reshape(M, N)[:orig_M, :orig_N].copy())

    if not batch_shape:
        return results[0]
    return np.stack(results).reshape(*batch_shape, *results[0].shape)
```

`_to_2d_batches` / `_prepare_2d` 在 `linear/__init__.py` 里是 module-level helper，复用时直接 import。

### 模板 C: 纯 Python（无 C 函数，例如 transpose）

参考 `src/dsp/ops/transpose/__init__.py`：`func` 参数会是 None（或 dummy），convention 内部自己用 `core.block` 完成所有变换。

## 自检清单

- [ ] 类定义带 `op="..."` 参数（自动注册）
- [ ] 变量名用 `dst / src0 / src1 / src2`，顺序和 C 对齐
- [ ] `dst` 是 `func(...)` 的第一个参数
- [ ] `output_shape` 正确处理 batch 前缀维度
- [ ] 矩阵类做了 pad + 分型 + crop，不留 padding 给 caller
- [ ] 没有做 double ↔ bf16 转换
- [ ] `python -c "from dsp.core.convention import _CONVENTIONS; print('my_op' in _CONVENTIONS)"` 为 True
- [ ] `python -m pytest tests/ut/ops -q` 全绿

## 边界情况

- 参数里有 scalar（如 `scale_exp`）：从 `params` 里取，或走装饰器传入的 kwargs
- 输出是多个 tensor：`output_shape` 返回 tuple of shapes，`call_c_func` 返回 tuple of numpy
- 如果 C 函数已在 `bind.cpp` 里内联做了 pad/unpad：convention 就只负责 batch 循环，别重复 pad
- 纯 Python convention（无 C）：`func` 参数用不上就忽略 —— 不要抛错

---
[操作员：在此行下方提供算子名 + C 函数签名 + 格式组合。]
