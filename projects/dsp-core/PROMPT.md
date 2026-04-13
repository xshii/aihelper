# dsp-core: 弱 AI 投喂手册

## 这是什么

> **信息安全声明：** 由于信息安全要求，强 AI 无法知道具体硬件细节。当前代码为架构示例，所有类型名、函数名、精度参数均为示意。

DSP 芯片验证框架。torch-like API，多模式验证（torch / pseudo_quant / golden_c）。

## 架构

```
golden_c/current/include/    # 硬件原始函数（不改，hardware reference only）
├── golden_convert.h         #   BINT8, BINT16, Q12_22 types
├── golden_matrix.h          #   sp_gemm hardware reference
└── golden_vector.h          #   sp_layernorm hardware reference

src/dsp/
├── core/
│   ├── dtype.py             # DType 枚举 + DSPDtype + TypeCodec（统一在此文件）
│   ├── enums.py             # Mode / Format / RunMode
│   ├── tensor.py            # DSPTensor
│   └── errors.py            # 自定义异常（带诊断信息）
├── golden/
│   ├── bind_helpers.h       # to_dut/from_dut traits（pybind11 桥接）
│   ├── bindings.cpp         # pybind11 入口（编译为 _raw_bindings.so）
│   ├── auto_register.py     # 从 _raw_bindings 扫描 dsp_* 函数，自动注册 manifest
│   ├── manifest.py          # ComputeKey + COMPUTE/CONVERT 表（auto_register 自动填充）
│   ├── call.py              # Python → C++ 调用
│   ├── dispatch.py          # batch 处理 + 模式分发
│   └── op_convention.py     # 参数映射约定（dst/src0/src1/src2 命名）
├── ops/                     # 每个 op 一个目录（Python + C++ 住一起，auto-import）
│   ├── __init__.py          #   pkgutil 自动导入所有 op 包
│   ├── _convert/            #   dsp_convert.h + bind.cpp（类型转换）
│   ├── linear/              #   __init__.py + dsp_matrix.h + bind.cpp（matmul + linear）
│   └── layernorm/           #   __init__.py + dsp_vector.h + bind.cpp（layernorm）
├── data/                    # DataPipe 链式 API + 工厂函数
└── config.py                # 全局配置
```

## 调用链路

```
dsp.ops.linear(x, w, b)
  → @register_op wrapper
    → mode == GOLDEN_C → dispatch_golden_c()
      → ComputeKey 查 manifest（auto_register 自动填充）
      → convention.call_c_func(func, ...)
        → _raw_bindings.dsp_linear_int16_int16_int16_int16_q12_22(dst, src0, src1, src2, ...)
          → ops/linear/dsp_matrix.h: dsp_linear<int16_t, int16_t, int16_t, int16_t, Q12_22>
            → golden_matrix.h: sp_fused_linear_int16_int16_bint16_oint16_acc_q12_22
```

## Golden C 模式运行流程

以 `dsp.ops.linear(x, w, b)` 在 golden_c 模式下为例：

```
① ops/linear/__init__.py — @register_op wrapper
   mode == GOLDEN_C → 进入 golden_c 路径

② golden/dispatch.py — 提取类型 + batch 处理
   从 DSPTensor 提取 src0_type="int16", src1_type="int16"
   x=[2,14,12] → batch=2，按 batch 循环调用

③ golden/call.py — manifest 查表
   ComputeKey(op="linear", src0="int16", src1="int16") -> 查 COMPUTE 表
   命中 "dsp_linear_int16_int16_int32_int16_q12_22"
   查 LinearConvention

④ golden/op_convention.py — 分型转换 + 拆参数 + 分配 dst
   float input [14,12] -> pad [16,16] -> ZZ block -> flatten
   float weight [12,8] -> pad [16,16] -> NN block -> flatten
   dst = np.zeros(M*N, dtype=float32)
   func(dst, src0, src1, src2, scale_exp, M, K, N)
   dst flat -> 去分型 -> 去 padding [14,8]

⑤ ops/linear/bind.cpp — float32 <-> typed int 转换（通过 trait 自动选 gc convert）
   to_dut<int16_t>(src0)    -> convert_float32_to_int16
   to_dut<int16_t>(src2)    -> convert_float32_to_int16
   调用 C 模板 -> 结果写入 vector<int16_t>
   from_dut(dst, d)         -> convert_int16_to_float32

⑥ ops/linear/dsp_matrix.h — 模板 wrapper
   dsp_linear<int16_t, int16_t, int16_t, int16_t, Q12_22>(
       out_zz, input_zz, weight_nn, bias_nd, ...)
   转发给硬件原始函数 ↓

⑦ golden_matrix.h — 硬件 C 计算
   sp_fused_linear_int16_int16_bint16_oint16_acc_q12_22(...)
   int64 累加 + clamp → 写入 dst
```

**分型转换在第4步（convention 层）**：调 C 前把 float ND 数据 pad + 分型(ZZ/NN)，调 C 后去分型 + 去 padding。已实现。

## 新增类型组合（零手动注册）

只需 2 步，manifest 自动注册：

```
步骤 1: src/dsp/ops/linear/dsp_matrix.h — 加一行模板特化
        template<> inline void dsp_linear<int8_t, int8_t, int16_t, int8_t, Q12_22>(...) 
        { sp_fused_linear_int8_int8_bint16_oint8_acc_q12_22(...); }

步骤 2: src/dsp/ops/linear/bind.cpp — 加一行绑定注册
        bind_linear<int8_t, int8_t, int16_t, int8_t, Q12_22>(
            m, "dsp_linear_int8_int8_int16_int8_q12_22");

步骤 3: make build-golden && make test
```

manifest.py 不用改（auto_register 从函数名自动解析 ComputeKey）。
@register_op 不用改（不需要 golden_c={...} 参数）。

## Golden C 接口约定

### 参数命名（ops/*/dsp_*.h 模板 wrapper）

参数名带角色 + 分型后缀，看签名就知道传什么：

```cpp
template<> inline void dsp_linear<int16_t, int16_t, int32_t, int16_t, Q12_22>(
    int16_t*       out_zz,      // 输出, ZZ 分块
    const int16_t* input_zz,    // 输入, ZZ 分块
    const int16_t* weight_nn,   // 权重, NN 分块
    const int32_t* bias_nd,     // 偏置, 不分块
    int scale_exp, int M, int K, int N)
```

分型后缀：
- `_zz` — Z 序分块（左矩阵/输出）
- `_nn` — 行优先分块（右矩阵/权重）
- `_nd` — 不分块（向量/bias）

### ACC 类型

`q12_22_t` 是独立的 C++ 类型（底层 int32，但与 DUT int 不同类型）。
binding 层的 `from_dut` trait 根据类型自动选正确的转换函数：
- `q12_22_t` → `convert_q12_22_to_float32`（ACC 定点解码）
- `int16_t` → `convert_int16_to_float32`（DUT 直接转）

### Block Padding（待适配）

当前 demo 直接操作 ND 数据。真实硬件接入时需在 convention 层做 block 转换：

```
调 C 前: input ND → _to_block(ZZ), weight ND → _to_block(NN)
调 C 后: output ZZ → _from_block(ND)
```

### ACC 比数

golden C 的输出是 ACC 格式，不能直接比数：

```
golden C 输出(ACC, block 格式)
  → 步骤 1: unpad（挤掉 block 填充）
  → 步骤 2: ACC → float32（调 dsp_q12_22_to_float32）
  → 步骤 3: 与 torch 结果比较
```

规则：
1. DO: ACC → float 必须调 golden C 提供的 `dsp_q*_to_float32`
   DON'T: 自己写 `raw / (1 << frac_bits)`
2. DO: 比数前先挤掉 block 对齐填充
   DON'T: 拿 padded 数据直接比
3. DO: 比数对象是 `dsp_q*_to_float32` 的输出 vs torch 结果
   DON'T: 拿 ACC 的 int32 和 torch 的 float32 直接比

## 最简用法

```python
import dsp

def main():
    x = dsp.data.randn(2, 14, 12, dtype=dsp.core.int16)
    w = dsp.data.randn(12, 8, dtype=dsp.core.int16)
    b = dsp.data.randn(1, 8, dtype=dsp.core.int16)
    return dsp.ops.linear(x, w, b)

dsp.context.run(main)
```

## 关键类型（统一在 core/dtype.py）

```python
from dsp.core.dtype import DType

# DUT — 芯片原生（数据存储）     ACC — 累加器（只有 Q 格式）
DType.DUT.INT8  (BINT8)           DType.ACC.Q12_22
DType.DUT.INT16 (BINT16)
```

```python
from dsp.core.enums import Mode, Format

Mode.TORCH / Mode.PSEUDO_QUANT / Mode.GOLDEN_C
Format.ZZ / Format.NN / Format.ND
```

## 自定义异常（带诊断信息）

```python
GoldenNotAvailable    # → make build-golden
ManifestNotFound      # → 显示已注册的类型组合 + 修复指导
ConventionNotFound    # → 显示已注册的 convention 列表 + 修复指导
```
