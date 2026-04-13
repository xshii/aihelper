#pragma once
#include <cstdint>
#include <cstring>

// ============================================================
// 硬件类型定义
//
// BF8:  fp8_e4m3 (1+4+3, range ±448)
// BF16: bfloat16 (1+8+7, range ±3.4e38)
// Q12_22: float32 累加器（模拟硬件 ACC，范围略大于 fp16）
// ============================================================

typedef struct { float raw; } Q12_22;

#define BF8_BLOCK_SIZE  16   // 128-bit / 8-bit  = 16 elements
#define BF16_BLOCK_SIZE  8   // 128-bit / 16-bit =  8 elements
typedef struct { uint8_t  val[BF8_BLOCK_SIZE];  } BF8;   // fp8_e4m3 bits
typedef struct { uint16_t val[BF16_BLOCK_SIZE]; } BF16;  // bfloat16 bits

// ============================================================
// 内部工具: bf16 / fp8 ↔ float
// ============================================================

// --- bfloat16: float32 高 16 位 ---
inline float bf16_to_float(uint16_t bf16) {
    uint32_t bits = (uint32_t)bf16 << 16;
    float f;
    memcpy(&f, &bits, sizeof(float));
    return f;
}

inline uint16_t float_to_bf16(float f) {
    uint32_t bits;
    memcpy(&bits, &f, sizeof(float));
    // round-to-nearest-even (和 torch .to(bfloat16) 一致)
    uint32_t lsb = (bits >> 16) & 1;
    uint32_t rounding_bias = 0x7FFF + lsb;
    bits += rounding_bias;
    return (uint16_t)(bits >> 16);
}

// --- fp8_e4m3: 1 sign + 4 exp (bias=7) + 3 mantissa, no inf, max=448 ---
inline float fp8_to_float(uint8_t fp8) {
    uint8_t sign = (fp8 >> 7) & 1;
    uint8_t exp = (fp8 >> 3) & 0xF;
    uint8_t man = fp8 & 0x7;
    if (exp == 0 && man == 0) return sign ? -0.0f : 0.0f;
    if (exp == 0) {
        // subnormal: (-1)^sign × 2^(-6) × (0.man)
        float val = (float)man / 8.0f * (1.0f / 64.0f);
        return sign ? -val : val;
    }
    // normal: (-1)^sign × 2^(exp-7) × (1.man)
    uint32_t f_exp = (uint32_t)(exp - 7 + 127);
    uint32_t f_bits = ((uint32_t)sign << 31) | (f_exp << 23) | ((uint32_t)man << 20);
    float f;
    memcpy(&f, &f_bits, sizeof(float));
    return f;
}

inline uint8_t float_to_fp8(float f) {
    uint32_t bits;
    memcpy(&bits, &f, sizeof(float));
    uint8_t sign = (bits >> 31) & 1;
    int32_t exp = ((bits >> 23) & 0xFF) - 127;
    uint32_t man = bits & 0x7FFFFF;

    if (f == 0.0f || f == -0.0f) return sign << 7;
    // clamp to fp8 range (max = 448)
    if (exp > 8) return (sign << 7) | 0x7E;  // max positive: s_1111_110 = ±448
    if (exp < -6) return sign << 7;  // underflow → ±0
    if (exp < -6 + 1) {
        // subnormal
        int shift = -6 - exp;
        uint8_t m = (uint8_t)((0x800000 | man) >> (20 + shift));
        return (sign << 7) | (m & 0x7);
    }
    uint8_t fp8_exp = (uint8_t)(exp + 7);
    uint8_t fp8_man = (uint8_t)(man >> 20) & 0x7;
    return (sign << 7) | (fp8_exp << 3) | fp8_man;
}

// ============================================================
// 参考实现（demo 用，真实硬件替换）
// ============================================================

#pragma region DUT<->DOUBLE

inline void BF8ToDouble(BF8 value, double *dst) {
    for (int i = 0; i < BF8_BLOCK_SIZE; i++)
        dst[i] = (double)fp8_to_float(value.val[i]);
}
inline void BF16ToDouble(BF16 value, double *dst) {
    for (int i = 0; i < BF16_BLOCK_SIZE; i++)
        dst[i] = (double)bf16_to_float(value.val[i]);
}

inline BF8 DoubleToBF8(double *src) {
    BF8 r;
    for (int i = 0; i < BF8_BLOCK_SIZE; i++)
        r.val[i] = float_to_fp8((float)src[i]);
    return r;
}
inline BF16 DoubleToBF16(double *src) {
    BF16 r;
    for (int i = 0; i < BF16_BLOCK_SIZE; i++)
        r.val[i] = float_to_bf16((float)src[i]);
    return r;
}

#pragma endregion

#pragma region ACC<->DUT

inline void acc_q12_22_to_bf8(Q12_22 *src, BF8 *dst) {
    for (int i = 0; i < BF8_BLOCK_SIZE; i++)
        dst->val[i] = float_to_fp8(src[i].raw);
}
inline void acc_q12_22_to_bf16(Q12_22 *src, BF16 *dst) {
    for (int i = 0; i < BF16_BLOCK_SIZE; i++)
        dst->val[i] = float_to_bf16(src[i].raw);
}

inline void bf8_to_acc_q12_22(BF8 *src, Q12_22 *dst) {
    for (int i = 0; i < BF8_BLOCK_SIZE; i++)
        dst[i].raw = fp8_to_float(src->val[i]);
}
inline void bf16_to_acc_q12_22(BF16 *src, Q12_22 *dst) {
    for (int i = 0; i < BF16_BLOCK_SIZE; i++)
        dst[i].raw = bf16_to_float(src->val[i]);
}

#pragma endregion
