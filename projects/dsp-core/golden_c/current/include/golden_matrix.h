#pragma once
#include <cstddef>
#include "golden_convert.h"

// 硬件矩阵运算（参考实现）
// src0 (input): ZZ 行优先存储，索引 a[m*K+k]
// src1 (weight): NN 列优先存储，索引 b[n*K+k]
// dst (output):  ZZ 行优先存储，索引 dst[m*N+n]
// 累加在 float32 (Q12_22.raw) 中进行

#define SP_GEMM_ACC_Q12_22(DUT, name, elem_t, to_float)                              \
inline void sp_gemm_##name##_acc_q12_22(                                             \
    Q12_22 *dst, DUT *src0, DUT *src1,                                               \
    DUT *bias, int scale_exp, size_t M, size_t K, size_t N) {                        \
    elem_t *a = (elem_t *)src0;  /* ZZ: row-major */                                 \
    elem_t *b = (elem_t *)src1;  /* NN: col-major */                                 \
    elem_t *bi = bias ? (elem_t *)bias : nullptr;                                    \
    for (size_t m = 0; m < M; m++)                                                   \
        for (size_t n = 0; n < N; n++) {                                             \
            float acc = 0.0f;                                                        \
            for (size_t k = 0; k < K; k++)                                           \
                acc += to_float(a[m*K+k]) * to_float(b[n*K+k]);                     \
            if (bi) acc += to_float(bi[n]) * (float)(1 << scale_exp);                \
            dst[m*N+n].raw = acc;                                                    \
        }                                                                            \
}

SP_GEMM_ACC_Q12_22(BF8,  bf8,  uint8_t,  fp8_to_float)
SP_GEMM_ACC_Q12_22(BF16, bf16, uint16_t, bf16_to_float)

#undef SP_GEMM_ACC_Q12_22
