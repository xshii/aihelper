#pragma once
#include "dsp/dsp_types.h"

// ============================================================
// 硬件转换接口（参考实现）
//
// 三类接口，签名各不相同：
//
// 1. double_to_dut: 返回 DUT 值，double 入参，逐元素，无 count
//    调用方按 block size 计算 DUT 内存偏移
//    int16_t gc_double_to_int16(double val);
//
// 2. dut_to_double: DUT 值入参，double 指针出参
//    void gc_int16_to_double(int16_t val, double* out);
//
// 3. acc_to_dut: ACC 指针 + DUT 指针 + 附加参数
//    void gc_q12_22_to_int16(int16_t* dst_zz, const int32_t* src_acc, int M, int N);
//
// ACC 和 double 都是非 block 型（flat ND）
// DUT 是 block 型（ZZ/NN）
// ============================================================


// ============================================================
// double_to_dut — 逐元素，返回 DUT 值
// ============================================================

inline int8_t gc_double_to_int8(double val) {
    if (val > 127.0) return 127;
    if (val < -128.0) return -128;
    return static_cast<int8_t>(val > 0 ? val + 0.5 : val - 0.5);
}

inline int16_t gc_double_to_int16(double val) {
    if (val > 32767.0) return 32767;
    if (val < -32768.0) return -32768;
    return static_cast<int16_t>(val > 0 ? val + 0.5 : val - 0.5);
}

inline int32_t gc_double_to_int32(double val) {
    if (val > 2147483647.0) return 2147483647;
    if (val < -2147483648.0) return -2147483648;
    return static_cast<int32_t>(val > 0 ? val + 0.5 : val - 0.5);
}


// ============================================================
// dut_to_double — DUT 值入参，double 指针出参
// ============================================================

inline void gc_int8_to_double(int8_t val, double* out) {
    *out = static_cast<double>(val);
}

inline void gc_int16_to_double(int16_t val, double* out) {
    *out = static_cast<double>(val);
}

inline void gc_int32_to_double(int32_t val, double* out) {
    *out = static_cast<double>(val);
}


// ============================================================
// acc_to_dut — ACC 指针 → DUT 指针
//   ACC 是 flat（ND），DUT 输出也是 flat（block 排列由调用方处理）
// ============================================================

inline void gc_q12_22_to_int16(int16_t* dst, const q12_22_t* src, int count) {
    for (int i = 0; i < count; i++) {
        Q12_22 acc(static_cast<int64_t>(src[i].raw));
        dst[i] = acc.to_int16();
    }
}

inline void gc_q12_22_to_int32(int32_t* dst, const q12_22_t* src, int count) {
    for (int i = 0; i < count; i++) {
        Q12_22 acc(static_cast<int64_t>(src[i].raw));
        dst[i] = acc.to_int32();
    }
}

inline void gc_q24_40_to_int32(int32_t* dst, const q24_40_t* src, int count) {
    for (int i = 0; i < count; i++) {
        Q24_40 acc(static_cast<int64_t>(src[i].raw));
        dst[i] = acc.to_int32();
    }
}



// ============================================================
// acc_to_float32 — ACC → float32（比数用）
// ============================================================

inline void gc_q12_22_to_double(double* dst, const q12_22_t* src, int count) {
    for (int i = 0; i < count; i++) {
        Q12_22 acc(static_cast<int64_t>(src[i].raw));
        dst[i] = acc.to_double();
    }
}

inline void gc_q24_40_to_double(double* dst, const q24_40_t* src, int count) {
    for (int i = 0; i < count; i++) {
        Q24_40 acc(static_cast<int64_t>(src[i].raw));
        dst[i] = acc.to_double();
    }
}


// ============================================================
// 批量便捷函数 — 内部循环调用逐元素接口
// 供 binding 层 to_typed / write_back 使用
// ============================================================

inline void convert_double_to_int8(int8_t* dst, const double* src, int count) {
    for (int i = 0; i < count; i++) dst[i] = gc_double_to_int8(static_cast<double>(src[i]));
}
inline void convert_double_to_int16(int16_t* dst, const double* src, int count) {
    for (int i = 0; i < count; i++) dst[i] = gc_double_to_int16(static_cast<double>(src[i]));
}
inline void convert_double_to_int32(int32_t* dst, const double* src, int count) {
    for (int i = 0; i < count; i++) dst[i] = gc_double_to_int32(static_cast<double>(src[i]));
}

inline void convert_int8_to_double(double* dst, const int8_t* src, int count) {
    for (int i = 0; i < count; i++) { double d; gc_int8_to_double(src[i], &d); dst[i] = static_cast<double>(d); }
}
inline void convert_int16_to_double(double* dst, const int16_t* src, int count) {
    for (int i = 0; i < count; i++) { double d; gc_int16_to_double(src[i], &d); dst[i] = static_cast<double>(d); }
}
inline void convert_int32_to_double(double* dst, const int32_t* src, int count) {
    for (int i = 0; i < count; i++) { double d; gc_int32_to_double(src[i], &d); dst[i] = static_cast<double>(d); }
}

inline void convert_q12_22_to_double(double* dst, const q12_22_t* src, int count) {
    gc_q12_22_to_double(dst, src, count);
}
inline void convert_q24_40_to_double(double* dst, const q24_40_t* src, int count) {
    gc_q24_40_to_double(dst, src, count);
}

// DUT ↔ DUT
inline void convert_int8_to_int16(int16_t* dst, const int8_t* src, int count) {
    for (int i = 0; i < count; i++) { double d; gc_int8_to_double(src[i], &d); dst[i] = gc_double_to_int16(d); }
}
inline void convert_int16_to_int8(int8_t* dst, const int16_t* src, int count) {
    for (int i = 0; i < count; i++) { double d; gc_int16_to_double(src[i], &d); dst[i] = gc_double_to_int8(d); }
}
inline void convert_int16_to_int32(int32_t* dst, const int16_t* src, int count) {
    for (int i = 0; i < count; i++) { double d; gc_int16_to_double(src[i], &d); dst[i] = gc_double_to_int32(d); }
}
inline void convert_int32_to_int16(int16_t* dst, const int32_t* src, int count) {
    for (int i = 0; i < count; i++) { double d; gc_int32_to_double(src[i], &d); dst[i] = gc_double_to_int16(d); }
}
