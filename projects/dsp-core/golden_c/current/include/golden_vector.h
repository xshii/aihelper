#pragma once
#include "dsp/dsp_types.h"

// 硬件向量运算函数（参考实现）

inline void sp_vadd_int16(BINT16* dst, const BINT16* src0, const BINT16* src1, int count) {
    for (int i = 0; i < count; i++)
        dst[i] = static_cast<int16_t>(std::clamp(static_cast<int32_t>(src0[i]) + src1[i], -32768, 32767));
}
inline void sp_vadd_int32(BINT32* dst, const BINT32* src0, const BINT32* src1, int count) {
    for (int i = 0; i < count; i++)
        dst[i] = static_cast<int32_t>(std::clamp(static_cast<int64_t>(src0[i]) + src1[i], (int64_t)-2147483648LL, (int64_t)2147483647LL));
}
inline void sp_vmul_int16_int16_oint32_acc_q12_22(
    q12_22_t* dst, const BINT16* src0, const BINT16* src1, int count) {
    for (int i = 0; i < count; i++)
        dst[i].raw = static_cast<int32_t>(std::clamp(static_cast<int64_t>(src0[i]) * src1[i], (int64_t)-2147483648LL, (int64_t)2147483647LL));
}
inline void sp_abs_int16(BINT16* dst, const BINT16* src0, int count) {
    for (int i = 0; i < count; i++) dst[i] = (src0[i] < 0) ? -src0[i] : src0[i];
}
inline void sp_abs_int32(BINT32* dst, const BINT32* src0, int count) {
    for (int i = 0; i < count; i++) dst[i] = (src0[i] < 0) ? -src0[i] : src0[i];
}
inline void sp_xcorr_int16_int16_oint32_acc_q12_22(
    q12_22_t* dst, const BINT16* src0, const BINT16* src1, int signal_len) {
    for (int i = 0; i < signal_len; i++) dst[i].raw = static_cast<int32_t>(src0[i]);
}
inline void sp_xcorr_int32_int32_oint32_acc_q24_40(
    q24_40_t* dst, const BINT32* src0, const BINT32* src1, int signal_len) {
    for (int i = 0; i < signal_len; i++) dst[i].raw = src0[i];
}
