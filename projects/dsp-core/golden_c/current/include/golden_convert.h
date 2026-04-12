#pragma once
#include <cstdint>
#include "dsp/dsp_types.h"

// ============================================================
// 硬件类型定义（纯 C 风格，平铺）
// ============================================================

typedef struct { int32_t raw; } Q12_22;
typedef struct { int32_t raw; } Q24_40;

typedef struct { int8_t  val[DSP_BLOCK_BYTES / sizeof(int8_t)];  } BINT8;   // 16 元素
typedef struct { int16_t val[DSP_BLOCK_BYTES / sizeof(int16_t)]; } BINT16;  // 8 元素
typedef struct { int32_t val[DSP_BLOCK_BYTES / sizeof(int32_t)]; } BINT32;  // 4 元素

// ============================================================
// 硬件转换接口 — 每次操作一个 subblock（一个 BINT = 128 bits）
// ============================================================

// DUT → double
void BINT8ToDouble(BINT8 value, double *dst);
void BINT16ToDouble(BINT16 value, double *dst);
void BINT32ToDouble(BINT32 value, double *dst);

// double → DUT
BINT8  DoubleToBINT8(double *src);
BINT16 DoubleToBINT16(double *src);
BINT32 DoubleToBINT32(double *src);

// ACC → DUT（一个 subblock）
void acc_q12_22_to_bint8(Q12_22 *src, BINT8 *dst);
void acc_q12_22_to_bint16(Q12_22 *src, BINT16 *dst);
void acc_q12_22_to_bint32(Q12_22 *src, BINT32 *dst);
void acc_q24_40_to_bint32(Q24_40 *src, BINT32 *dst);


// ============================================================
// 参考实现（demo 用，真实硬件替换）
// ============================================================

inline void BINT8ToDouble(BINT8 value, double *dst) {
    for (int i = 0; i < DSP_BLOCK_BYTES / (int)sizeof(int8_t); i++)
        dst[i] = (double)value.val[i];
}
inline void BINT16ToDouble(BINT16 value, double *dst) {
    for (int i = 0; i < DSP_BLOCK_BYTES / (int)sizeof(int16_t); i++)
        dst[i] = (double)value.val[i];
}
inline void BINT32ToDouble(BINT32 value, double *dst) {
    for (int i = 0; i < DSP_BLOCK_BYTES / (int)sizeof(int32_t); i++)
        dst[i] = (double)value.val[i];
}

inline BINT8 DoubleToBINT8(double *src) {
    BINT8 r;
    for (int i = 0; i < DSP_BLOCK_BYTES / (int)sizeof(int8_t); i++)
        r.val[i] = (src[i] > 127) ? 127 : (src[i] < -128) ? -128 : (int8_t)(src[i] + (src[i] > 0 ? 0.5 : -0.5));
    return r;
}
inline BINT16 DoubleToBINT16(double *src) {
    BINT16 r;
    for (int i = 0; i < DSP_BLOCK_BYTES / (int)sizeof(int16_t); i++)
        r.val[i] = (src[i] > 32767) ? 32767 : (src[i] < -32768) ? -32768 : (int16_t)(src[i] + (src[i] > 0 ? 0.5 : -0.5));
    return r;
}
inline BINT32 DoubleToBINT32(double *src) {
    BINT32 r;
    for (int i = 0; i < DSP_BLOCK_BYTES / (int)sizeof(int32_t); i++)
        r.val[i] = (src[i] > 2147483647.0) ? 2147483647 : (src[i] < -2147483648.0) ? -2147483648 : (int32_t)(src[i] + (src[i] > 0 ? 0.5 : -0.5));
    return r;
}

inline void acc_q12_22_to_bint8(Q12_22 *src, BINT8 *dst) {
    for (int i = 0; i < DSP_BLOCK_BYTES / (int)sizeof(int8_t); i++) {
        int64_t s = (int64_t)src[i].raw >> 22;
        dst->val[i] = (s > 127) ? 127 : (s < -128) ? -128 : (int8_t)s;
    }
}
inline void acc_q12_22_to_bint16(Q12_22 *src, BINT16 *dst) {
    for (int i = 0; i < DSP_BLOCK_BYTES / (int)sizeof(int16_t); i++) {
        int64_t s = (int64_t)src[i].raw >> 22;
        dst->val[i] = (s > 32767) ? 32767 : (s < -32768) ? -32768 : (int16_t)s;
    }
}
inline void acc_q12_22_to_bint32(Q12_22 *src, BINT32 *dst) {
    for (int i = 0; i < DSP_BLOCK_BYTES / (int)sizeof(int32_t); i++) {
        int64_t s = (int64_t)src[i].raw >> 22;
        dst->val[i] = (s > 2147483647LL) ? 2147483647 : (s < -2147483648LL) ? -2147483648 : (int32_t)s;
    }
}
inline void acc_q24_40_to_bint32(Q24_40 *src, BINT32 *dst) {
    for (int i = 0; i < DSP_BLOCK_BYTES / (int)sizeof(int32_t); i++) {
        int64_t s = (int64_t)src[i].raw >> 40;
        dst->val[i] = (s > 2147483647LL) ? 2147483647 : (s < -2147483648LL) ? -2147483648 : (int32_t)s;
    }
}
