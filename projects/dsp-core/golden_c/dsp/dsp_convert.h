#pragma once
#include "include/golden_convert.h"

// ============================================================
// dsp_convert<Src, Dst>(dst_ptr, src_ptr, count)
//
// Python 只看到 DUT block 类型 + float + double
// ACC 相关转换仅在 dsp_matrix.h / dsp_vector.h 内部使用
// ============================================================

template<typename Src, typename Dst>
void dsp_convert(Dst* dst, const Src* src, int count);

// --- float → DUT ---
template<> inline void dsp_convert<double, int8_t>(int8_t* dst, const double* src, int count) {
    convert_double_to_int8(dst, src, count);
}
template<> inline void dsp_convert<double, int16_t>(int16_t* dst, const double* src, int count) {
    convert_double_to_int16(dst, src, count);
}
template<> inline void dsp_convert<double, int32_t>(int32_t* dst, const double* src, int count) {
    convert_double_to_int32(dst, src, count);
}

// --- DUT → float ---
template<> inline void dsp_convert<int8_t, double>(double* dst, const int8_t* src, int count) {
    convert_int8_to_double(dst, src, count);
}
template<> inline void dsp_convert<int16_t, double>(double* dst, const int16_t* src, int count) {
    convert_int16_to_double(dst, src, count);
}
template<> inline void dsp_convert<int32_t, double>(double* dst, const int32_t* src, int count) {
    convert_int32_to_double(dst, src, count);
}

// --- DUT → DUT ---
template<> inline void dsp_convert<int8_t, int16_t>(int16_t* dst, const int8_t* src, int count) {
    convert_int8_to_int16(dst, src, count);
}
template<> inline void dsp_convert<int16_t, int8_t>(int8_t* dst, const int16_t* src, int count) {
    convert_int16_to_int8(dst, src, count);
}
template<> inline void dsp_convert<int16_t, int32_t>(int32_t* dst, const int16_t* src, int count) {
    convert_int16_to_int32(dst, src, count);
}
template<> inline void dsp_convert<int32_t, int16_t>(int16_t* dst, const int32_t* src, int count) {
    convert_int32_to_int16(dst, src, count);
}

// --- DUT block → double（比数用，调 gc 逐元素接口）---
template<> inline void dsp_convert<bint8, double>(double* dst, const bint8* src, int count) {
    const int8_t* p = reinterpret_cast<const int8_t*>(src);
    for (int i = 0; i < count; i++) gc_int8_to_double(p[i], &dst[i]);
}
template<> inline void dsp_convert<bint16, double>(double* dst, const bint16* src, int count) {
    const int16_t* p = reinterpret_cast<const int16_t*>(src);
    for (int i = 0; i < count; i++) gc_int16_to_double(p[i], &dst[i]);
}
template<> inline void dsp_convert<bint32, double>(double* dst, const bint32* src, int count) {
    const int32_t* p = reinterpret_cast<const int32_t*>(src);
    for (int i = 0; i < count; i++) gc_int32_to_double(p[i], &dst[i]);
}

// --- double → DUT block（调 gc 逐元素接口）---
template<> inline void dsp_convert<double, bint8>(bint8* dst, const double* src, int count) {
    int8_t* p = reinterpret_cast<int8_t*>(dst);
    for (int i = 0; i < count; i++) p[i] = gc_double_to_int8(src[i]);
}
template<> inline void dsp_convert<double, bint16>(bint16* dst, const double* src, int count) {
    int16_t* p = reinterpret_cast<int16_t*>(dst);
    for (int i = 0; i < count; i++) p[i] = gc_double_to_int16(src[i]);
}
template<> inline void dsp_convert<double, bint32>(bint32* dst, const double* src, int count) {
    int32_t* p = reinterpret_cast<int32_t*>(dst);
    for (int i = 0; i < count; i++) p[i] = gc_double_to_int32(src[i]);
}

