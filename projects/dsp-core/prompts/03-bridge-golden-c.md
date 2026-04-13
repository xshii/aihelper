# 接入新的 Golden C 函数

## 角色
你是一个硬件验证工程师，负责把硬件团队的 C 参考函数接入框架。

## 任务
硬件团队提供新的 `sp_*` 函数时，完成三件事：

1. 在 `src/dsp/ops/<op>/dsp_*.h` 添加模板特化（wrapper）
2. 在 `src/dsp/ops/<op>/bind.cpp` 添加 pybind11 导出
3. 重编译 `_raw_bindings.so`（`make build-golden`）

**manifest 注册是自动的** —— `src/dsp/golden/auto_register.py` 启动时扫描 `_raw_bindings` 里所有 `dsp_*` 函数名，回填 `manifest.COMPUTE` / `manifest.CONVERT`。**不要** 手动改 `manifest.py`。

## 目录结构

```
golden_c/current/include/             # 硬件原始参考（不改）
├── golden_convert.h                  #   BF8 / BF16 structs, 类型转换
├── golden_matrix.h                   #   sp_gemm_bf16_acc_q12_22 等
└── golden_vector.h                   #   sp_layernorm 等

src/dsp/ops/                          # 每个 op 一个目录（Python + C++ 住一起）
├── _convert/                         #   dsp_convert.h + bind.cpp（类型转换入口）
├── linear/                           #   dsp_matrix.h + bind.cpp（matmul + linear）
├── layernorm/                        #   dsp_vector.h + bind.cpp
└── transpose/                        #   纯 Python，无 bind.cpp

src/dsp/golden/
├── bind_helpers.h                    # to_dut / from_dut / num_blocks 模板
├── bindings.cpp                      # pybind11 顶层入口
└── auto_register.py                  # 从 _raw_bindings 反射注册 manifest
```

## 命名规则（auto_register 的唯一依据）

```
Compute 函数:    dsp_{op}_{dut_name}              e.g. dsp_matmul_bf16, dsp_linear_bf8
Convert 函数:    dsp_convert_{src}_{dst}          e.g. dsp_convert_bf16_double
```

`auto_register.py` 按这个规则从函数名反解出 `ComputeKey(op=..., src0=..., dst0=...)` 并填表。**函数名错了 = manifest 没注册 = `require_compute_info` 抛 `ManifestNotFound`**。

## 模板特化的类型参数

`dsp_matrix.h` 里的模板：

```cpp
template<typename Src0, typename Src1, typename Dst0>
void dsp_matmul(Dst0* out_zz, Src0* input_zz, Src1* weight_nn,
                size_t M, size_t K, size_t N);

template<typename Src0, typename Src1, typename Src2, typename Dst0>
void dsp_linear(Dst0* out_zz, Src0* input_zz, Src1* weight_nn,
                Src2* bias_nd, int scale_exp, size_t M, size_t K, size_t N);
```

参数名后缀 = 格式分型：`_zz`=Z序分块, `_nn`=列优先分块, `_nd`=不分块。

累加器（ACC）在模板特化内部隐藏，不作为模板参数：硬件的 Q12_22 累加器是 `float32` 包装，特化里 `std::vector<ACC>` 临时存储，最后 `dsp_convert<DUT, ACC>` 收回。

## 步骤

### 步骤 1: `src/dsp/ops/<op>/dsp_*.h` 添加模板特化

找到对应 op 目录下的 `dsp_*.h`，照已有特化改类型和 golden C 函数名：

```cpp
// src/dsp/ops/linear/dsp_matrix.h
#define DSP_MATMUL_LINEAR(DUT, ACC, GemmFn)                                          \
template<> inline void dsp_matmul<DUT, DUT, DUT>(                                    \
    DUT* out_zz, DUT* input_zz, DUT* weight_nn, size_t M, size_t K, size_t N) {     \
    std::vector<ACC> acc(M * N);                                                     \
    GemmFn(acc.data(), input_zz, weight_nn, nullptr, 0, M, K, N);                    \
    dsp_convert<DUT, ACC>(out_zz, acc.data(), M * N);                                \
}                                                                                    \
/* dsp_linear 同理 */

DSP_MATMUL_LINEAR(BF8,  Q12_22, sp_gemm_bf8_acc_q12_22)
DSP_MATMUL_LINEAR(BF16, Q12_22, sp_gemm_bf16_acc_q12_22)
```

### 步骤 2: `src/dsp/ops/<op>/bind.cpp` 添加 pybind11 导出

```cpp
// src/dsp/ops/linear/bind.cpp
#define BIND_MATMUL_LINEAR(DUT, dut_name)                                            \
    m.def("dsp_matmul_" #dut_name,                                                   \
        [](py::array_t<double> dst, py::array_t<double> input,                       \
           py::array_t<double> weight, size_t M, size_t K, size_t N) {               \
            auto input_dut  = to_dut<DUT>(input);                                    \
            auto weight_dut = to_dut<DUT>(weight);                                   \
            std::vector<DUT> out(num_blocks<DUT>(M * N));                            \
            dsp_matmul<DUT, DUT, DUT>(out.data(),                                    \
                input_dut.data(), weight_dut.data(), M, K, N);                       \
            from_dut(dst, out, M * N);                                               \
        });

void bind_matrix(py::module& m) {
    BIND_MATMUL_LINEAR(BF8,  bf8)
    BIND_MATMUL_LINEAR(BF16, bf16)
}
```

### 步骤 3: 重编译 + 验证

```bash
make build-golden                         # cmake + build → _raw_bindings.so
python -c "from dsp.golden.call import _get_lib; print(hasattr(_get_lib(), 'dsp_matmul_bf16'))"
python -c "import dsp; from dsp.golden.manifest import COMPUTE; print([k for k in COMPUTE if k.op=='matmul'])"
python -m pytest tests/ut -q
```

## Examples

### Example 1: 为 matmul 添加 `bf4 × bf4 → bf4` 变体

**前提:** 硬件团队给了 `sp_gemm_bf4_acc_q12_22`，签名和 `sp_gemm_bf16_*` 一致。

**`src/dsp/ops/linear/dsp_matrix.h` 加一行宏调用:**
```cpp
DSP_MATMUL_LINEAR(BF4, Q12_22, sp_gemm_bf4_acc_q12_22)
```

**`src/dsp/ops/linear/bind.cpp` 加一行宏调用:**
```cpp
BIND_MATMUL_LINEAR(BF4, bf4)
```

**不用改:**
- `manifest.py`（auto_register 扫描 `dsp_matmul_bf4` → 自动填 `ComputeKey(op="matmul", src0="bf4", dst0="bf4")`）
- `@register_op`（装饰器没有 `golden_c=`）
- Python 侧的 `LinearConvention`（和 dtype 无关，只关心格式）
- 前提: `bf4` 这个 DSPDtype 已经通过 prompt 05 注册，`BF4` 这个 C++ 类型已在 `golden_convert.h` 里定义

### Example 2: convert 函数（double ↔ DUT）

新类型的 convert 走 `src/dsp/ops/_convert/`，绑定函数名必须严格是 `dsp_convert_double_{dtype}` 和 `dsp_convert_{dtype}_double`：

```cpp
// src/dsp/ops/_convert/bind.cpp
m.def("dsp_convert_double_bf4", ...);
m.def("dsp_convert_bf4_double", ...);
```

`auto_register._register_convert` 按这个规则反解为 `CONVERT[("double", "bf4")] = "dsp_convert_double_bf4"`。

## 常见错误

| 错误 | 症状 | 修复 |
|---|---|---|
| 绑定函数名不符合 `dsp_{op}_{dut}` | auto_register 不认 → manifest 里找不到 → 跑 op 抛 `ManifestNotFound` | 按命名规则改 |
| 模板特化类型顺序与 golden 签名不符 | 编译错 / 运行时结果错 | 核对 `golden_*.h` 里的签名 |
| 忘了 `inline` | 多 TU 链接时重复定义 | 特化前加 `inline` |
| 特化用了不存在的类型组合 | 链接时 undefined reference | 确认 `golden_*.h` 里有对应函数 |
| 改完没重编译 | `.so` 还是老的，新函数缺席 | `make build-golden` |
| `ComputeKey` 里的 dtype 名大小写不对 | `auto_register` 用的是 `DType.DUT.value`（小写），不要手动填 | 不用手填 —— auto_register 负责 |

## 自检清单

- [ ] `src/dsp/ops/<op>/dsp_*.h` 里的模板特化编译通过
- [ ] `src/dsp/ops/<op>/bind.cpp` 里新增的 `m.def` 名字严格遵循 `dsp_{op}_{dut_name}`
- [ ] `make build-golden` 成功
- [ ] `python -c "from dsp.golden.call import _get_lib; print('dsp_{op}_{dut}' in dir(_get_lib()))"` 为 True
- [ ] `python -c "from dsp.golden.manifest import COMPUTE; print(COMPUTE)"` 里看到新条目
- [ ] `python -m pytest tests/ut/golden -q` 全绿

## 边界情况

- golden_c 不可用时框架会自动 fallback 到 torch 参考实现 —— 不影响开发
- 如果硬件签名完全不一样（参数个数/顺序不同）：**先按 prompt 06 注册新的 OpConvention**，再回来做 bind
- 如果需要的 dtype 还没有：先走 prompt 05 加 DSPDtype + prompt 01 注册 Codec，再做 bind

---
[操作员：在此行下方提供 op 名、新的 dtype 组合、golden 函数名。]
