#pragma once
#include <cstdint>
#include <cmath>
#include <algorithm>

// ============================================================
// 定点类型（bit pattern 存在 float 里传输，内部按整数运算）
// ============================================================

inline int16_t to_iq16(float v) {
    float clamped = std::clamp(v, -32768.0f, 32767.0f);
    return static_cast<int16_t>(std::round(clamped));
}

inline int32_t to_iq32(float v) {
    double clamped = std::clamp(static_cast<double>(v), -2147483648.0, 2147483647.0);
    return static_cast<int32_t>(std::round(clamped));
}

inline float from_iq16(int16_t v) { return static_cast<float>(v); }
inline float from_iq32(int32_t v) { return static_cast<float>(v); }

// ============================================================
// Convert
// ============================================================

inline void convert_float32_to_iq16(const float* src, float* dst, int count) {
    for (int i = 0; i < count; i++)
        dst[i] = from_iq16(to_iq16(src[i]));
}

inline void convert_iq16_to_float32(const float* src, float* dst, int count) {
    for (int i = 0; i < count; i++)
        dst[i] = src[i];  // iq16 bit pattern 已经在 float 里
}

inline void convert_float32_to_iq32(const float* src, float* dst, int count) {
    for (int i = 0; i < count; i++)
        dst[i] = static_cast<float>(to_iq32(src[i]));
}

inline void convert_iq32_to_float32(const float* src, float* dst, int count) {
    for (int i = 0; i < count; i++)
        dst[i] = src[i];
}

inline void convert_iq16_to_iq32(const float* src, float* dst, int count) {
    for (int i = 0; i < count; i++)
        dst[i] = src[i];  // 值不变，精度提升
}

inline void convert_iq32_to_iq16(const float* src, float* dst, int count) {
    for (int i = 0; i < count; i++)
        dst[i] = from_iq16(to_iq16(src[i]));  // 截断
}

// ============================================================
// Compute: matmul
//   A[M,K] x B[K,N] = C[M,N]
//   ACC 精度: Q12.22 模拟（用 double 累加，最后截断）
// ============================================================

inline void sp_gemm_iq16_iq16_oiq32_acc_q12_22(
    const float* a, const float* b, float* out, int M, int K, int N)
{
    for (int m = 0; m < M; m++) {
        for (int n = 0; n < N; n++) {
            double acc = 0.0;  // Q12.22 用 double 模拟
            for (int k = 0; k < K; k++)
                acc += static_cast<double>(to_iq16(a[m*K+k])) * to_iq16(b[k*N+n]);
            out[m*N+n] = static_cast<float>(to_iq32(static_cast<float>(acc)));
        }
    }
}

inline void sp_gemm_iq16_iq16_oiq16_acc_q12_22(
    const float* a, const float* b, float* out, int M, int K, int N)
{
    for (int m = 0; m < M; m++) {
        for (int n = 0; n < N; n++) {
            double acc = 0.0;
            for (int k = 0; k < K; k++)
                acc += static_cast<double>(to_iq16(a[m*K+k])) * to_iq16(b[k*N+n]);
            out[m*N+n] = from_iq16(to_iq16(static_cast<float>(acc)));
        }
    }
}

inline void sp_gemm_iq32_iq32_oiq32_acc_q24_40(
    const float* a, const float* b, float* out, int M, int K, int N)
{
    for (int m = 0; m < M; m++) {
        for (int n = 0; n < N; n++) {
            double acc = 0.0;
            for (int k = 0; k < K; k++)
                acc += static_cast<double>(a[m*K+k]) * a[k*N+n];
            out[m*N+n] = static_cast<float>(to_iq32(static_cast<float>(acc)));
        }
    }
}

// ============================================================
// Compute: fused linear (matmul + bias + scale)
// ============================================================

inline void sp_fused_linear_iq16_iq16_biq32_oiq16_acc_q12_22(
    const float* a, const float* b, const float* bias, float* out,
    int scale_exp, int M, int K, int N)
{
    for (int m = 0; m < M; m++) {
        for (int n = 0; n < N; n++) {
            double acc = 0.0;
            for (int k = 0; k < K; k++)
                acc += static_cast<double>(to_iq16(a[m*K+k])) * to_iq16(b[k*N+n]);
            acc += static_cast<double>(to_iq32(bias[n]));  // bias in ACC precision
            // scale: shift by scale_exp (简化版)
            out[m*N+n] = from_iq16(to_iq16(static_cast<float>(acc)));
        }
    }
}

inline void sp_fused_linear_iq16_iq16_biq32_oiq32_acc_q12_22(
    const float* a, const float* b, const float* bias, float* out,
    int scale_exp, int M, int K, int N)
{
    for (int m = 0; m < M; m++) {
        for (int n = 0; n < N; n++) {
            double acc = 0.0;
            for (int k = 0; k < K; k++)
                acc += static_cast<double>(to_iq16(a[m*K+k])) * to_iq16(b[k*N+n]);
            acc += static_cast<double>(to_iq32(bias[n]));
            out[m*N+n] = static_cast<float>(to_iq32(static_cast<float>(acc)));
        }
    }
}

inline void sp_fused_linear_iq32_iq32_biq32_oiq32_acc_q24_40(
    const float* a, const float* b, const float* bias, float* out,
    int scale_exp, int M, int K, int N)
{
    for (int m = 0; m < M; m++) {
        for (int n = 0; n < N; n++) {
            double acc = 0.0;
            for (int k = 0; k < K; k++)
                acc += static_cast<double>(a[m*K+k]) * a[k*N+n];
            acc += static_cast<double>(bias[n]);
            out[m*N+n] = static_cast<float>(to_iq32(static_cast<float>(acc)));
        }
    }
}

// ============================================================
// Compute: elementwise
// ============================================================

inline void sp_vadd_iq16(const float* a, const float* b, float* out, int count) {
    for (int i = 0; i < count; i++)
        out[i] = from_iq16(to_iq16(a[i] + b[i]));
}

inline void sp_vadd_iq32(const float* a, const float* b, float* out, int count) {
    for (int i = 0; i < count; i++)
        out[i] = static_cast<float>(to_iq32(a[i] + b[i]));
}

inline void sp_vmul_iq16_iq16_oiq32_acc_q12_22(
    const float* a, const float* b, float* out, int count)
{
    for (int i = 0; i < count; i++) {
        double r = static_cast<double>(to_iq16(a[i])) * to_iq16(b[i]);
        out[i] = static_cast<float>(to_iq32(static_cast<float>(r)));
    }
}

// ============================================================
// Compute: abs
// ============================================================

inline void sp_abs_iq16(const float* x, float* out, int count) {
    for (int i = 0; i < count; i++)
        out[i] = std::abs(x[i]);
}

inline void sp_abs_iq32(const float* x, float* out, int count) {
    for (int i = 0; i < count; i++)
        out[i] = std::abs(x[i]);
}

// ============================================================
// Compute: correlate
// ============================================================

inline void sp_xcorr_iq16_iq16_oiq32_acc_q12_22(
    const float* a, const float* b, float* out, int signal_len)
{
    // 简化：假设 b_len 从输出大小推算
    // 实际需要额外参数，这里用 signal_len 做全相关
    for (int i = 0; i < signal_len; i++) {
        out[i] = static_cast<float>(to_iq32(a[i]));  // 占位
    }
}

inline void sp_xcorr_iq32_iq32_oiq32_acc_q24_40(
    const float* a, const float* b, float* out, int signal_len)
{
    for (int i = 0; i < signal_len; i++) {
        out[i] = static_cast<float>(to_iq32(a[i]));
    }
}
