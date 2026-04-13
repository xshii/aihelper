#pragma once
#include <cstddef>
#include "golden_vector.h"
#include "dsp_convert.h"

// ComputeType: 中间计算精度（golden 参考实现统一用 double 模拟）
enum class ComputeType { INT32, FP16 };

#pragma region LAYERNORM_1D

// LayerNorm1D: 按 cols 维做 normalize
//   out[b,m,r,c] = gamma[c] * (input[b,m,r,c] - mean[b,m,r]) / std[b,m,r] + beta[c]
// shape: (batch, matrix, rows, cols)
// gamma / beta shape: (cols_mem,) —— cols_mem = pad_dim(cols, BlockSize)

template<typename DUT, ComputeType CT>
void dsp_layernorm1d(DUT* out, DUT* input, DUT* gamma, DUT* beta,
                     size_t batch, size_t matrix, size_t rows, size_t cols);

#define DSP_LAYERNORM1D(DUT, CT, GoldenFn)                                           \
template<> inline void dsp_layernorm1d<DUT, CT>(                                     \
    DUT* out, DUT* input, DUT* gamma, DUT* beta,                                     \
    size_t batch, size_t matrix, size_t rows, size_t cols) {                         \
    GoldenFn(out, input, gamma, beta, batch, matrix, rows, cols);                    \
}

DSP_LAYERNORM1D(BF8,  ComputeType::INT32, sp_layernorm1d_bf8_acc_q12_22)
DSP_LAYERNORM1D(BF16, ComputeType::INT32, sp_layernorm1d_bf16_acc_q12_22)

#undef DSP_LAYERNORM1D

#pragma endregion
