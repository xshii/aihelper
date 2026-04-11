#pragma once
#include "../dsp/dsp_types.h"

// 硬件类型转换函数（参考实现）

// ACC → float32
inline void convert_q12_22_to_float32(float* dst, const q12_22_t* src, int count) {
    for (int i = 0; i < count; i++) {
        Q12_22 acc(static_cast<int64_t>(src[i].raw));
        dst[i] = static_cast<float>(acc.to_double());
    }
}
inline void convert_q24_40_to_float32(float* dst, const q24_40_t* src, int count) {
    for (int i = 0; i < count; i++) {
        Q24_40 acc(static_cast<int64_t>(src[i].raw));
        dst[i] = static_cast<float>(acc.to_double());
    }
}

// float32 ↔ int8/int16/int32
inline void convert_float32_to_int8(int8_t* dst, const float* src, int count) {
    for (int i = 0; i < count; i++)
        dst[i] = static_cast<int8_t>(std::clamp(std::round(src[i]), -128.0f, 127.0f));
}
inline void convert_int8_to_float32(float* dst, const int8_t* src, int count) {
    for (int i = 0; i < count; i++) dst[i] = static_cast<float>(src[i]);
}
inline void convert_float32_to_int16(int16_t* dst, const float* src, int count) {
    for (int i = 0; i < count; i++)
        dst[i] = static_cast<int16_t>(std::clamp(std::round(src[i]), -32768.0f, 32767.0f));
}
inline void convert_int16_to_float32(float* dst, const int16_t* src, int count) {
    for (int i = 0; i < count; i++) dst[i] = static_cast<float>(src[i]);
}
inline void convert_float32_to_int32(int32_t* dst, const float* src, int count) {
    for (int i = 0; i < count; i++) {
        double c = std::clamp(static_cast<double>(src[i]), -2147483648.0, 2147483647.0);
        dst[i] = static_cast<int32_t>(std::round(c));
    }
}
inline void convert_int32_to_float32(float* dst, const int32_t* src, int count) {
    for (int i = 0; i < count; i++) dst[i] = static_cast<float>(src[i]);
}

// int ↔ int
inline void convert_int8_to_int16(int16_t* dst, const int8_t* src, int count) {
    for (int i = 0; i < count; i++) dst[i] = static_cast<int16_t>(src[i]);
}
inline void convert_int16_to_int8(int8_t* dst, const int16_t* src, int count) {
    for (int i = 0; i < count; i++)
        dst[i] = static_cast<int8_t>(std::clamp(static_cast<int>(src[i]), -128, 127));
}
inline void convert_int16_to_int32(int32_t* dst, const int16_t* src, int count) {
    for (int i = 0; i < count; i++) dst[i] = static_cast<int32_t>(src[i]);
}
inline void convert_int32_to_int16(int16_t* dst, const int32_t* src, int count) {
    for (int i = 0; i < count; i++)
        dst[i] = static_cast<int16_t>(std::clamp(src[i], -32768, 32767));
}
