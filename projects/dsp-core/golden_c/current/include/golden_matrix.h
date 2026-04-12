#pragma once
#include "golden_convert.h"

// 硬件矩阵运算（参考实现）
// 签名用 BINT*，内部 cast 成 int16_t*/int32_t* flat 索引

inline void sp_gemm_int16_int16_oint32_acc_q12_22(
    Q12_22 *dst, const BINT16 *src0, const BINT16 *src1, int M, int K, int N) {
    const int16_t *a = (const int16_t *)src0, *b = (const int16_t *)src1;
    for (int m = 0; m < M; m++)
        for (int n = 0; n < N; n++) {
            int64_t acc = 0;
            for (int k = 0; k < K; k++) acc += (int64_t)a[m*K+k] * b[k*N+n];
            dst[m*N+n].raw = (int32_t)(acc > 2147483647LL ? 2147483647 : acc < -2147483648LL ? -2147483648 : acc);
        }
}

inline void sp_gemm_int16_int16_oint16_acc_q12_22(
    BINT16 *dst, const BINT16 *src0, const BINT16 *src1, int M, int K, int N) {
    const int16_t *a = (const int16_t *)src0, *b = (const int16_t *)src1;
    int16_t *d = (int16_t *)dst;
    for (int m = 0; m < M; m++)
        for (int n = 0; n < N; n++) {
            int64_t acc = 0;
            for (int k = 0; k < K; k++) acc += (int64_t)a[m*K+k] * b[k*N+n];
            d[m*N+n] = (int16_t)(acc > 32767 ? 32767 : acc < -32768 ? -32768 : acc);
        }
}

inline void sp_gemm_int32_int32_oint32_acc_q24_40(
    Q24_40 *dst, const BINT32 *src0, const BINT32 *src1, int M, int K, int N) {
    const int32_t *a = (const int32_t *)src0, *b = (const int32_t *)src1;
    for (int m = 0; m < M; m++)
        for (int n = 0; n < N; n++) {
            int64_t acc = 0;
            for (int k = 0; k < K; k++) acc += (int64_t)a[m*K+k] * b[k*N+n];
            dst[m*N+n].raw = (int32_t)(acc > 2147483647LL ? 2147483647 : acc < -2147483648LL ? -2147483648 : acc);
        }
}

inline void sp_fused_linear_int16_int16_bint32_oint16_acc_q12_22(
    BINT16 *dst, const BINT16 *src0, const BINT16 *src1,
    const BINT32 *src2, int scale_exp, int M, int K, int N) {
    const int16_t *a = (const int16_t *)src0, *b = (const int16_t *)src1;
    const int32_t *bias = (const int32_t *)src2;
    int16_t *d = (int16_t *)dst;
    for (int m = 0; m < M; m++)
        for (int n = 0; n < N; n++) {
            int64_t acc = 0;
            for (int k = 0; k < K; k++) acc += (int64_t)a[m*K+k] * b[k*N+n];
            acc += (int64_t)bias[n];
            d[m*N+n] = (int16_t)(acc > 32767 ? 32767 : acc < -32768 ? -32768 : acc);
        }
}

inline void sp_fused_linear_int16_int16_bint32_oint32_acc_q12_22(
    Q12_22 *dst, const BINT16 *src0, const BINT16 *src1,
    const BINT32 *src2, int scale_exp, int M, int K, int N) {
    const int16_t *a = (const int16_t *)src0, *b = (const int16_t *)src1;
    const int32_t *bias = (const int32_t *)src2;
    for (int m = 0; m < M; m++)
        for (int n = 0; n < N; n++) {
            int64_t acc = 0;
            for (int k = 0; k < K; k++) acc += (int64_t)a[m*K+k] * b[k*N+n];
            acc += (int64_t)bias[n];
            dst[m*N+n].raw = (int32_t)(acc > 2147483647LL ? 2147483647 : acc < -2147483648LL ? -2147483648 : acc);
        }
}

inline void sp_fused_linear_int32_int32_bint32_oint32_acc_q24_40(
    Q24_40 *dst, const BINT32 *src0, const BINT32 *src1,
    const BINT32 *src2, int scale_exp, int M, int K, int N) {
    const int32_t *a = (const int32_t *)src0, *b = (const int32_t *)src1;
    const int32_t *bias = (const int32_t *)src2;
    for (int m = 0; m < M; m++)
        for (int n = 0; n < N; n++) {
            int64_t acc = 0;
            for (int k = 0; k < K; k++) acc += (int64_t)a[m*K+k] * b[k*N+n];
            acc += (int64_t)bias[n];
            dst[m*N+n].raw = (int32_t)(acc > 2147483647LL ? 2147483647 : acc < -2147483648LL ? -2147483648 : acc);
        }
}
