#pragma once
#include <cmath>
#include <cstddef>
#include <vector>
#include "golden_convert.h"

// 硬件向量运算（参考实现）
//
// LayerNorm1D: 按 cols 维做 normalize
//   out[b,m,r,c] = gamma[c] * (input[b,m,r,c] - mean[b,m,r]) / sqrt(var + eps) + beta[c]
//
// 参数:
//   batch, matrix, rows: 独立 norm 组数的三个外层维度
//   cols: reduction / feature 维的逻辑长度
//
// 内存布局约定（caller 负责）:
//   cols_mem = pad_dim(cols, BlockSize)          -- 每行对齐后的 memory 宽度
//   input / dst 按 (batch, matrix, rows, cols_mem) 行优先存，subblock 索引
//   gamma / beta 按 (cols_mem,) 存
//   总 subblock 数 = batch * matrix * rows * cols_mem / BlockSize
//
// reduction 范围:
//   每行对前 cols 个元素求 mean/var，padding 区 [cols .. cols_mem) 不进统计。
//   （caller 通过 "padded_shape_mode" 开关选择是传 orig_cols 还是 padded_cols：
//    传 padded_cols → cols_mem == cols → reduction 把 padding 0 也算进去（有偏）。）

#define SP_LAYERNORM1D_ACC_Q12_22(DUT, name, BlockSize, ToDbl, FromDbl)                \
inline void sp_layernorm1d_##name##_acc_q12_22(                                        \
    DUT *dst, DUT *input, DUT *gamma, DUT *beta,                                       \
    size_t batch, size_t matrix, size_t rows, size_t cols) {                           \
    size_t cols_mem = cols + (BlockSize - cols % BlockSize) % BlockSize;               \
    size_t n_samples = batch * matrix * rows;                                          \
    size_t total_mem = n_samples * cols_mem;                                           \
    size_t total_subs = total_mem / BlockSize;                                         \
    size_t gamma_subs = cols_mem / BlockSize;                                          \
    std::vector<double> x(total_mem), g(cols_mem), b(cols_mem), out(total_mem);        \
    for (size_t s = 0; s < total_subs; s++)                                            \
        ToDbl(input[s], x.data() + s * BlockSize);                                     \
    for (size_t s = 0; s < gamma_subs; s++) {                                          \
        ToDbl(gamma[s], g.data() + s * BlockSize);                                     \
        ToDbl(beta[s],  b.data() + s * BlockSize);                                     \
    }                                                                                  \
    for (size_t r = 0; r < n_samples; r++) {                                           \
        double *row_x = x.data() + r * cols_mem;                                       \
        double *row_o = out.data() + r * cols_mem;                                     \
        double mean = 0;                                                               \
        for (size_t c = 0; c < cols; c++) mean += row_x[c];                            \
        mean /= cols;                                                                  \
        double var = 0;                                                                \
        for (size_t c = 0; c < cols; c++)                                              \
            var += (row_x[c] - mean) * (row_x[c] - mean);                              \
        var /= cols;                                                                   \
        double inv_std = 1.0 / sqrt(var + 1e-5);                                       \
        for (size_t c = 0; c < cols; c++)                                              \
            row_o[c] = g[c] * (row_x[c] - mean) * inv_std + b[c];                      \
        /* row_o[cols..cols_mem) 保持 std::vector 默认 0 */                            \
    }                                                                                  \
    for (size_t s = 0; s < total_subs; s++)                                            \
        dst[s] = FromDbl(out.data() + s * BlockSize);                                  \
}

SP_LAYERNORM1D_ACC_Q12_22(BF8,  bf8,  BF8_BLOCK_SIZE,  BF8ToDouble,  DoubleToBF8)
SP_LAYERNORM1D_ACC_Q12_22(BF16, bf16, BF16_BLOCK_SIZE, BF16ToDouble, DoubleToBF16)

#undef SP_LAYERNORM1D_ACC_Q12_22
