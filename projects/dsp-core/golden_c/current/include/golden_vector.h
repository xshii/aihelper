#pragma once
#include "golden_convert.h"

// 硬件向量运算（参考实现）

inline void sp_vadd_int16(BINT16 *dst, const BINT16 *src0, const BINT16 *src1, int count) {
    int16_t *d = (int16_t *)dst;
    const int16_t *a = (const int16_t *)src0, *b = (const int16_t *)src1;
    for (int i = 0; i < count; i++)
        d[i] = (int16_t)((int32_t)a[i] + b[i] > 32767 ? 32767 : (int32_t)a[i] + b[i] < -32768 ? -32768 : a[i] + b[i]);
}

inline void sp_vadd_int32(BINT32 *dst, const BINT32 *src0, const BINT32 *src1, int count) {
    int32_t *d = (int32_t *)dst;
    const int32_t *a = (const int32_t *)src0, *b = (const int32_t *)src1;
    for (int i = 0; i < count; i++) {
        int64_t r = (int64_t)a[i] + b[i];
        d[i] = (int32_t)(r > 2147483647LL ? 2147483647 : r < -2147483648LL ? -2147483648 : r);
    }
}

inline void sp_vmul_int16_int16_oint32_acc_q12_22(
    Q12_22 *dst, const BINT16 *src0, const BINT16 *src1, int count) {
    const int16_t *a = (const int16_t *)src0, *b = (const int16_t *)src1;
    for (int i = 0; i < count; i++) {
        int64_t r = (int64_t)a[i] * b[i];
        dst[i].raw = (int32_t)(r > 2147483647LL ? 2147483647 : r < -2147483648LL ? -2147483648 : r);
    }
}

inline void sp_abs_int16(BINT16 *dst, const BINT16 *src0, int count) {
    int16_t *d = (int16_t *)dst;
    const int16_t *a = (const int16_t *)src0;
    for (int i = 0; i < count; i++) d[i] = (a[i] < 0) ? -a[i] : a[i];
}

inline void sp_abs_int32(BINT32 *dst, const BINT32 *src0, int count) {
    int32_t *d = (int32_t *)dst;
    const int32_t *a = (const int32_t *)src0;
    for (int i = 0; i < count; i++) d[i] = (a[i] < 0) ? -a[i] : a[i];
}

inline void sp_xcorr_int16_int16_oint32_acc_q12_22(
    Q12_22 *dst, const BINT16 *src0, const BINT16 *src1, int signal_len) {
    const int16_t *a = (const int16_t *)src0;
    for (int i = 0; i < signal_len; i++) dst[i].raw = (int32_t)a[i];
}

inline void sp_xcorr_int32_int32_oint32_acc_q24_40(
    Q24_40 *dst, const BINT32 *src0, const BINT32 *src1, int signal_len) {
    const int32_t *a = (const int32_t *)src0;
    for (int i = 0; i < signal_len; i++) dst[i].raw = a[i];
}
