# 添加算子调用约定（OpConvention）

## 角色
你是一个 Python 工程师，负责告诉框架一个新算子的 C 函数如何调用。

## 任务
当 C 函数的参数模式和已有的 Convention 不同时，注册一个新的 OpConvention。

## 已有 Convention

| Convention | 适用 | C 签名 | 分型 |
|-----------|------|--------|------|
| UnaryConvention | abs | func(dst, src0, count) | ND |
| ElementwiseConvention | add, mul, sub | func(dst, src0, src1, count) | ND |
| MatmulConvention | matmul | func(dst_zz, input_zz, weight_nn, M, K, N) | ZZ+NN |
| LinearConvention | linear | func(dst_zz, input_zz, weight_nn, bias_nd, scale, M, K, N) | ZZ+NN+ND |
| CorrelateConvention | correlate | func(dst, signal, template, signal_len) | ND |

**何时需要新 Convention？**
- 先看上表，参数模式一样 → 直接在 `op=` 列表加名字
- 参数个数/顺序/分型不同 → 新建

## Convention 职责

Convention 处理完整的输入输出流程:
```
输入: float → pad → 分型(ZZ/NN) → flatten → [传给 binding]
输出: [binding 返回] → 去分型 → 去 padding → 返回
```

binding 层处理 float↔DUT 类型转换，convention 不用管。

## 规则
1. DO: 变量名用 `dst, src0, src1, src2`（与硬件 C 接口一致）
2. DO: `dst` 放第一个参数传给 C 函数
3. DO: 矩阵运算需要 pad + 分型（复用 `_pad_2d`, `_to_blocked`, `_from_blocked`）
4. DON'T: 在 Convention 里做类型转换（binding 层做）

## 模板

```python
class MyConvention(OpConvention, op="my_op"):
    """func(dst, src0, src1, N)"""

    def output_shape(self, *inputs):
        return inputs[0].shape

    def call_c_func(self, func, *inputs_np, **params):
        src0 = inputs_np[0].flatten()
        src1 = inputs_np[1].flatten()
        N = src0.size
        dst = np.zeros(N, dtype=np.float32)
        func(dst, src0, src1, N)
        return dst
```

矩阵运算模板（需要分型）:

```python
class MyMatrixConvention(OpConvention, op="my_matrix_op"):
    """func(dst_zz, input_zz, weight_nn, M, K, N)"""

    def output_shape(self, *inputs):
        return (*inputs[0].shape[:-1], inputs[1].shape[-1])

    def call_c_func(self, func, *inputs_np, **params):
        src0, src1 = inputs_np[0], inputs_np[1]
        orig_M, K, orig_N = src0.shape[-2], src0.shape[-1], src1.shape[-1]

        key = params.get("compute_key")
        dtype_name = str(key.src0) if key else "int16"
        bh, bw = _get_block_shape(dtype_name, "zz")

        # float → pad → 分型 → flatten
        src0_blocked = _to_blocked(_pad_2d(src0, bh, bw), bh, bw)
        src1_blocked = _to_blocked(_pad_2d(src1, bh, bw), bh, bw)

        M = _pad_dim(orig_M, bh)
        K_padded = _pad_dim(K, bw)
        N = _pad_dim(orig_N, bw)
        dst_flat = np.zeros(M * N, dtype=np.float32)

        func(dst_flat, src0_blocked, src1_blocked, M, K_padded, N)

        # → 去分型 → 去 padding
        dst_2d = _from_blocked(dst_flat, bh, bw, M, N)
        return _unpad_2d(dst_2d, orig_M, orig_N)
```

## 自检清单
- [ ] 变量名用 `dst, src0, src1, src2`
- [ ] `func(dst, ...)` — dst 第一位
- [ ] 矩阵运算: pad → 分型 → C → 去分型 → unpad
- [ ] `op="name"` 在类定义处（自动注册）
- [ ] `make test` 通过
