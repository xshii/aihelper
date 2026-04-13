#pragma once
#include <cmath>
#include <cstddef>
#include "golden_convert.h"

// 硬件矩阵运算（参考实现）
//
// src0 (input / activation): ZZ 行优先存储，索引 a[m*K+k]，类型 DUT_A
// src1 (weight):             NN 列优先存储，索引 b[n*K+k]，类型 DUT_W（可 ≠ DUT_A）
// bias:                      DUT_A，跟 input 同精度
// dst:                       Q12_22 累加输出，由调用方转回 DUT_A
//
// 统一形式 sp_gemm_<dut_a>_dutw_<dut_w>_acc_q12_22
// 同构情形 dut_a == dut_w 也用这个命名（例如 sp_gemm_bf8_dutw_bf8_acc_q12_22）。

#define SP_GEMM_ACC_Q12_22(DUT_A, name_a, elem_a, to_float_a,                        \
                           DUT_W, name_w, elem_w, to_float_w)                        \
inline void sp_gemm_##name_a##_dutw_##name_w##_acc_q12_22(                           \
    Q12_22 *dst, DUT_A *src0, DUT_W *src1,                                           \
    DUT_A *bias, int scale_exp, size_t M, size_t K, size_t N) {                      \
    elem_a *a = (elem_a *)src0;                                                      \
    elem_w *b = (elem_w *)src1;                                                      \
    elem_a *bi = bias ? (elem_a *)bias : nullptr;                                    \
    for (size_t m = 0; m < M; m++)                                                   \
        for (size_t n = 0; n < N; n++) {                                             \
            float acc = 0.0f;                                                        \
            for (size_t k = 0; k < K; k++)                                           \
                acc += to_float_a(a[m*K+k]) * to_float_w(b[n*K+k]);                 \
            if (bi) acc += to_float_a(bi[n]) * ldexpf(1.0f, scale_exp);              \
            dst[m*N+n].raw = acc;                                                    \
        }                                                                            \
}

// 实例化：同构 bf8×bf8, bf16×bf16 + 异构 bf16×bf8
SP_GEMM_ACC_Q12_22(BF8,  bf8,  uint8_t,  fp8_to_float,
                   BF8,  bf8,  uint8_t,  fp8_to_float)
SP_GEMM_ACC_Q12_22(BF16, bf16, uint16_t, bf16_to_float,
                   BF16, bf16, uint16_t, bf16_to_float)
SP_GEMM_ACC_Q12_22(BF16, bf16, uint16_t, bf16_to_float,
                   BF8,  bf8,  uint8_t,  fp8_to_float)

#undef SP_GEMM_ACC_Q12_22
