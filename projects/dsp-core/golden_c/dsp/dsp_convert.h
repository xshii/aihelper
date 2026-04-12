#pragma once
#include "include/golden_convert.h"

// bint = BINT 别名
typedef BINT8  bint8;
typedef BINT16 bint16;
typedef BINT32 bint32;

// ACC 别名（dsp 层用小写）
typedef Q12_22 q12_22_t;
typedef Q24_40 q24_40_t;

// subblock size
static constexpr int BINT8_SIZE  = DSP_BLOCK_BYTES / sizeof(int8_t);   // 16
static constexpr int BINT16_SIZE = DSP_BLOCK_BYTES / sizeof(int16_t);  // 8
static constexpr int BINT32_SIZE = DSP_BLOCK_BYTES / sizeof(int32_t);  // 4

// ============================================================
// dsp_convert<Src, Dst>(dst, src, count)
// 按 subblock 循环调用硬件接口
// count = 总元素数（不是 subblock 数）
// ============================================================

template<typename Src, typename Dst>
void dsp_convert(Dst* dst, const Src* src, int count);

// --- double → bint（每 N 个 double → 一个 BINT）---
template<> inline void dsp_convert<double, bint8>(bint8* dst, const double* src, int count) {
    for (int i = 0; i < count; i += BINT8_SIZE)
        dst[i / BINT8_SIZE] = DoubleToBINT8(const_cast<double*>(src + i));
}
template<> inline void dsp_convert<double, bint16>(bint16* dst, const double* src, int count) {
    for (int i = 0; i < count; i += BINT16_SIZE)
        dst[i / BINT16_SIZE] = DoubleToBINT16(const_cast<double*>(src + i));
}
template<> inline void dsp_convert<double, bint32>(bint32* dst, const double* src, int count) {
    for (int i = 0; i < count; i += BINT32_SIZE)
        dst[i / BINT32_SIZE] = DoubleToBINT32(const_cast<double*>(src + i));
}

// --- bint → double（一个 BINT → N 个 double）---
template<> inline void dsp_convert<bint8, double>(double* dst, const bint8* src, int count) {
    for (int i = 0; i < count; i += BINT8_SIZE)
        BINT8ToDouble(src[i / BINT8_SIZE], dst + i);
}
template<> inline void dsp_convert<bint16, double>(double* dst, const bint16* src, int count) {
    for (int i = 0; i < count; i += BINT16_SIZE)
        BINT16ToDouble(src[i / BINT16_SIZE], dst + i);
}
template<> inline void dsp_convert<bint32, double>(double* dst, const bint32* src, int count) {
    for (int i = 0; i < count; i += BINT32_SIZE)
        BINT32ToDouble(src[i / BINT32_SIZE], dst + i);
}

// --- double identity ---
template<> inline void dsp_convert<double, double>(double* dst, const double* src, int count) {
    for (int i = 0; i < count; i++) dst[i] = src[i];
}
