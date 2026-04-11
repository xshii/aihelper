#pragma once
#include "../dsp/dsp_types.h"

// 硬件矩阵运算函数（参考实现）

// matmul
inline void sp_gemm_int16_int16_oint32_acc_q12_22(
    q12_22_t* dst, const int16_t* src0, const int16_t* src1, int M, int K, int N) {
    for (int m = 0; m < M; m++)
        for (int n = 0; n < N; n++) {
            int64_t acc = 0;
            for (int k = 0; k < K; k++) acc += static_cast<int64_t>(src0[m*K+k]) * src1[k*N+n];
            dst[m*N+n].raw = static_cast<int32_t>(std::clamp(acc, (int64_t)-2147483648LL, (int64_t)2147483647LL));
        }
}
inline void sp_gemm_int16_int16_oint16_acc_q12_22(
    int16_t* dst, const int16_t* src0, const int16_t* src1, int M, int K, int N) {
    for (int m = 0; m < M; m++)
        for (int n = 0; n < N; n++) {
            int64_t acc = 0;
            for (int k = 0; k < K; k++) acc += static_cast<int64_t>(src0[m*K+k]) * src1[k*N+n];
            dst[m*N+n] = static_cast<int16_t>(std::clamp(acc, (int64_t)-32768, (int64_t)32767));
        }
}
inline void sp_gemm_int32_int32_oint32_acc_q24_40(
    q24_40_t* dst, const int32_t* src0, const int32_t* src1, int M, int K, int N) {
    for (int m = 0; m < M; m++)
        for (int n = 0; n < N; n++) {
            int64_t acc = 0;
            for (int k = 0; k < K; k++) acc += static_cast<int64_t>(src0[m*K+k]) * src1[k*N+n];
            dst[m*N+n].raw = static_cast<int32_t>(std::clamp(acc, (int64_t)-2147483648LL, (int64_t)2147483647LL));
        }
}

// fused linear
inline void sp_fused_linear_int16_int16_bint32_oint16_acc_q12_22(
    int16_t* dst, const int16_t* src0, const int16_t* src1,
    const int32_t* src2, int scale_exp, int M, int K, int N) {
    for (int m = 0; m < M; m++)
        for (int n = 0; n < N; n++) {
            int64_t acc = 0;
            for (int k = 0; k < K; k++) acc += static_cast<int64_t>(src0[m*K+k]) * src1[k*N+n];
            acc += static_cast<int64_t>(src2[n]);
            dst[m*N+n] = static_cast<int16_t>(std::clamp(acc, (int64_t)-32768, (int64_t)32767));
        }
}
inline void sp_fused_linear_int16_int16_bint32_oint32_acc_q12_22(
    q12_22_t* dst, const int16_t* src0, const int16_t* src1,
    const int32_t* src2, int scale_exp, int M, int K, int N) {
    for (int m = 0; m < M; m++)
        for (int n = 0; n < N; n++) {
            int64_t acc = 0;
            for (int k = 0; k < K; k++) acc += static_cast<int64_t>(src0[m*K+k]) * src1[k*N+n];
            acc += static_cast<int64_t>(src2[n]);
            dst[m*N+n].raw = static_cast<int32_t>(std::clamp(acc, (int64_t)-2147483648LL, (int64_t)2147483647LL));
        }
}
inline void sp_fused_linear_int32_int32_bint32_oint32_acc_q24_40(
    q24_40_t* dst, const int32_t* src0, const int32_t* src1,
    const int32_t* src2, int scale_exp, int M, int K, int N) {
    for (int m = 0; m < M; m++)
        for (int n = 0; n < N; n++) {
            int64_t acc = 0;
            for (int k = 0; k < K; k++) acc += static_cast<int64_t>(src0[m*K+k]) * src1[k*N+n];
            acc += static_cast<int64_t>(src2[n]);
            dst[m*N+n].raw = static_cast<int32_t>(std::clamp(acc, (int64_t)-2147483648LL, (int64_t)2147483647LL));
        }
}
