# 接入新的 Golden C 函数

## 角色
你是一个硬件验证工程师，负责把硬件团队的 C 函数接入框架。

## 任务
当硬件团队提供新的 C 函数，完成以下两步：
1. 在 `golden_c/dsp/dsp_*.h` 添加模板特化（wrapper）
2. 在 `src/dsp/golden/bind_*.cpp` 添加一行绑定注册

manifest 自动注册（auto_register.py 从函数名解析），不用手改。

## 背景

### 目录结构

```
golden_c/
├── include/           # 硬件原始函数（不改）
│   ├── golden_matrix.h
│   └── golden_vector.h
├── dsp/               # 模板 wrapper（你要改的）
│   ├── dsp_types.h    # q12_22_t / q24_40_t 类型定义
│   ├── dsp_matrix.h   # matmul / linear wrapper
│   └── dsp_vector.h   # add / mul / abs / correlate wrapper

src/dsp/golden/
├── bind_matrix.cpp    # matmul / linear 绑定（你要改的）
├── bind_vector.cpp    # add / mul / abs / correlate 绑定
└── auto_register.py   # 从 _raw_bindings 扫描 dsp_* 自动注册 manifest
```

### 模板 wrapper 命名规则

```cpp
// dsp_matrix.h 中:
template<typename Src0, typename Src1, typename Dst0, typename Acc>
void dsp_matmul(Dst0* out_zz, const Src0* input_zz, const Src1* weight_nn, int M, int K, int N);

// 参数名后缀 = 分型: _zz = Z序分块, _nn = 行优先分块, _nd = 不分块
```

### Python 函数名编码规则

```
dsp_{op}_{src0_type}_{src1_type}_{dst0_type}_{acc_type}
例: dsp_matmul_int16_int16_q12_22_q12_22
```

auto_register.py 从这个名字自动解析出 ComputeKey 注册到 manifest，不用手写。

## 步骤

### 步骤 1: 在 dsp_*.h 添加模板特化

找到对应的 `dsp_*.h` 文件，照抄已有特化，改类型和 golden C 函数名：

```cpp
// golden_c/dsp/dsp_matrix.h
template<> inline void dsp_matmul<int8_t, int8_t, q12_22_t, Q12_22>(
    q12_22_t* out_zz, const int8_t* input_zz, const int8_t* weight_nn, int M, int K, int N)
{ sp_gemm_int8_int8_oint32_acc_q12_22(out_zz, input_zz, weight_nn, M, K, N); }
```

### 步骤 2: 在 bind_*.cpp 添加绑定

```cpp
// src/dsp/golden/bind_matrix.cpp
bind_gemm<int8_t, int8_t, q12_22_t, Q12_22>(m, "dsp_matmul_int8_int8_q12_22_q12_22");
```

### 步骤 3: 编译测试

```bash
make build-golden && make test
```

## 样例

### 样例: 为 matmul 添加 int8×int8 → q12_22 变体

假设硬件新增了 `sp_gemm_int8_int8_oint32_acc_q12_22`。

**dsp_matrix.h 添加:**
```cpp
template<> inline void dsp_matmul<int8_t, int8_t, q12_22_t, Q12_22>(
    q12_22_t* out_zz, const int8_t* input_zz, const int8_t* weight_nn, int M, int K, int N)
{ sp_gemm_int8_int8_oint32_acc_q12_22(out_zz, input_zz, weight_nn, M, K, N); }
```

**bind_matrix.cpp 添加:**
```cpp
bind_gemm<int8_t, int8_t, q12_22_t, Q12_22>(m, "dsp_matmul_int8_int8_q12_22_q12_22");
```

**不用改的:** manifest.py（auto_register 自动填），@register_op（不需要 golden_c 参数）

## 常见错误

| 错误 | 症状 | 修复 |
|------|------|------|
| 模板特化的类型和 golden C 签名不匹配 | 编译错误 | 核对 golden_*.h 中的函数签名 |
| 函数名中类型顺序错 | auto_register 解析出错误的 ComputeKey | 按 src0_src1_dst0_acc 顺序 |
| 忘了 inline | 链接时重复定义 | 特化前加 inline |
| 用了不存在的类型组合 | 链接时 undefined reference | 确认 golden_*.h 中有对应函数 |

## 自检清单
- [ ] dsp_*.h 特化编译通过
- [ ] bind_*.cpp 绑定名字格式正确: `dsp_{op}_{types}`
- [ ] `make build-golden` 编译成功
- [ ] `make test` 全绿
