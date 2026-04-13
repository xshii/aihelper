# DSP 数据流程（从磁盘出发）

状态三元组: **(dtype, isPadding, format)**

- **dtype**: `double` | `bf16` | `bf8`
- **isPadding**: `pad` | `no_pad`
- **format**: `nd`（row-major 原始）| `zz` | `nn`

---

## 核心原则

1. **内存里所有 tensor 全程 double**
2. **DSPDtype 只是个标签**，告诉框架这个 tensor 在硬件上会以什么格式存（bf16/bf8）
3. **torch mode 全程用 double 算**，通过前置量化模拟硬件精度
4. **只在和 C / 磁盘 DUT 交互时才真正转成 bf16 bits**

---

## 磁盘文件

| 文件 | 三元组 | 谁产生 |
|---|---|---|
| ND 文件 | `(double, no_pad, nd)` | GENERATE_INPUT / USE_INPUT 各模式 |
| DUT 文件 | `(bf16, pad, zz/nn)` | 外部硬件 / golden_c 中间结果 |

---

## RunMode: GENERATE_INPUT（torch 模式）

### randn 前置量化

每次 `randn(dtype=bf16)` 的输出要先"过一遍硬件"，把量化误差前置：

```
torch.randn (double, no_pad, nd)
  ↓ pad_to_block (依据 dtype 的 ZZ block_shape)
   (double, pad, nd)
  ↓ to_block ZZ
   (double, pad, zz)
  ↓ codec.from_float  (C: float→bf16)
   (bf16, pad, zz)
  ↓ codec.to_float    (C: bf16→double)
   (double, pad, zz)
  ↓ from_block
   (double, pad, nd)
  ↓ unpad
   (double, no_pad, nd)                    ← 存为 torch.float64 的 DSPTensor(bf16 标签)
```

### op 执行 + 保存

```
args (double, no_pad, nd)
  ↓ 纯 torch double 运算
result (double, no_pad, nd)

save_op_inputs / save_op_output:
  → 磁盘 ND 文件 (double, no_pad, nd)
```

---

## RunMode: USE_INPUT（读 ND 文件，重跑 pseudo_quant / golden_c）

### 加载

```
磁盘 ND 文件 (double, no_pad, nd)
  ↓
内存 DSPTensor (double, no_pad, nd, 标签=bf16)   ← 替换 op wrapper 的 args
```

### 执行（以 golden_c 的 linear 为例）

```
args (double, no_pad, nd)
  ↓ convention.pad_to_block
   (double, pad, nd)
  ↓ convention.to_block (input=ZZ, weight=NN)
   (double, pad, zz/nn)
  ↓ C binding to_dut<BF16>  (subblock 级: double→bf16 bits)
   (bf16, pad, zz/nn)                      ← C 内部
  ↓ sp_gemm_bf16 (float32 累加)
  ↓ dsp_convert<BF16, Q12_22>
   (bf16, pad, zz)                         ← C 输出
  ↓ from_dut               (subblock 级: bf16 bits→double)
   (double, pad, zz)
  ↓ convention.from_block + crop
   (double, no_pad, nd)                    ← op 输出
  → save_op_output: 磁盘 ND 文件
```

### 执行（pseudo_quant 模式）

```
args (double, no_pad, nd)
  ↓ fake_quantize (C: double→bf16→double，逐 tensor)
   (double, no_pad, nd, 但值已被 bf16 量化过)
  ↓ torch op (double)
result (double, no_pad, nd)
```

### 比数

```
GENERATE_INPUT 的 torch output    (double, no_pad, nd)
vs
USE_INPUT 的各模式 output         (double, no_pad, nd)
  ↓ compute_diff / compute_dut_exact
```

---

## RunMode: USE_INPUT_DUT（外部 DUT 文件）

### 加载

```
磁盘 DUT 文件 (bf16, pad, zz/nn)           ← 外部硬件产生
  ↓ 读 bf16 bits
  ↓ codec.to_float (subblock)
   (double, pad, zz/nn)
  ↓ from_block + unpad
   (double, no_pad, nd)                    ← 替换 wrapper args
```

### 执行 + 比数

三种 mode 各跑一次，比数两类：

1. **golden_c DUT bit 精确**: C 内部 `(bf16, pad, zz/nn)` vs 外部预期 `(bf16, pad, zz/nn)`
2. **double 比对**: 三路 `(double, no_pad, nd)` 互比

---

## 完整示例：2 层 linear

```python
out1 = linear(input, W1, b1)    # [4,8] × [8,6] + [1,6] → [4,6]
out2 = linear(out1, W2, b2)     # [4,6] × [6,4] + [1,4] → [4,4]
```

bf16 block_shape: ZZ=(16,16), NN=(16,32)

### GENERATE_INPUT（torch 模式，写 double 文件）

```
randn(input) → 前置量化 round-trip → (double, no_pad, nd)[4,8]
randn(W1)    → 前置量化            → (double, no_pad, nd)[8,6]
randn(b1)    → 前置量化            → (double, no_pad, nd)[1,6]

linear_0 (torch double 计算):
  out1 = input @ W1 + b1          → (double, no_pad, nd)[4,6]
  save:
    linear_0_input0_bf16_4x8_nd.txt   ← (double, no_pad, nd)
    linear_0_input1_bf16_8x6_nd.txt
    linear_0_input2_bf16_1x6_nd.txt
    linear_0_output0_bf16_4x6_nd.txt

randn(W2), randn(b2) → 前置量化

linear_1:
  input0 = out1                    (double, no_pad, nd)[4,6]
  out2 = out1 @ W2 + b2           (double, no_pad, nd)[4,4]
  save linear_1_input0~2 + output0
```

### USE_INPUT + golden_c（读 double，跑 C，写 double 输出）

```
linear_0:
  加载 input/W1/b1 (double, no_pad, nd)     ← 从磁盘
  ↓ pad + to_block ZZ/NN → (double, pad, zz/nn)
  ↓ to_dut<BF16>           → (bf16, pad, zz/nn)  C 内部
  ↓ sp_gemm_bf16
  ↓ from_dut               → (double, pad, zz)
  ↓ from_block + crop      → (double, no_pad, nd)[4,6]
  save linear_0_output0_bf16_4x6_nd.txt (double)

linear_1:
  加载 input0/W2/b2 (double, no_pad, nd)     ← 从磁盘（不用上面算的 out1）
  同上流程
  save linear_1_output0_bf16_4x4_nd.txt (double)
```

### 比数

```
GENERATE torch 的 linear_0_output0 (double)
vs
USE_INPUT golden_c 的 linear_0_output0 (double)
  → compute_diff
```

---

## 关键规则

1. **内存 tensor 全程 double**（不管 DSPDtype 标签是什么）
2. **randn 生成后立即前置量化**（pad→block→bf16→double→unblock→unpad），把量化误差打进输入
3. **磁盘 ND 文件存 double**（nd 原始 shape，无 padding）
4. **bf16 bits 只在 C 内部和 DUT 文件里存在**
5. **bf16 ↔ double 必须走 C codec**，不用 torch 原生转换
