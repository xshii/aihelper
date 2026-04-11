#pragma once
#include <cstdint>
#include <cmath>
#include <algorithm>

// ============================================================
// ACC 定点格式 + 存储类型
// ============================================================

template<int INT_BITS, int FRAC_BITS>
struct QFormat {
    static constexpr int int_bits  = INT_BITS;
    static constexpr int frac_bits = FRAC_BITS;
    int64_t raw = 0;

    QFormat() = default;
    explicit QFormat(int64_t v) : raw(v) {}

    static QFormat from_mul(int16_t a, int16_t b) { return QFormat{static_cast<int64_t>(a) * b}; }
    static QFormat from_mul(int32_t a, int32_t b) { return QFormat{static_cast<int64_t>(a) * b}; }

    void add(QFormat other) { raw += other.raw; }
    void add(int32_t bias)  { raw += static_cast<int64_t>(bias) << FRAC_BITS; }

    double to_double() const { return static_cast<double>(raw) / (1LL << FRAC_BITS); }

    int16_t to_int16() const {
        int64_t s = raw >> FRAC_BITS;
        return static_cast<int16_t>(std::clamp(s, static_cast<int64_t>(-32768), static_cast<int64_t>(32767)));
    }
    int32_t to_int32() const {
        int64_t s = raw >> FRAC_BITS;
        return static_cast<int32_t>(std::clamp(s, static_cast<int64_t>(-2147483648LL), static_cast<int64_t>(2147483647LL)));
    }
};

using Q12_22 = QFormat<12, 22>;
using Q24_40 = QFormat<24, 40>;

// ACC 存储类型 — 底层 int32，与 DUT int32 是不同 C++ 类型
struct q12_22_t { int32_t raw; };
struct q24_40_t { int32_t raw; };


// ============================================================
// Block 类型 — DUT 值 + block shape 编译期绑定
//
// 不同 DUT 类型的 block size 不同:
//   int8  zz=(32,32)  nn=(32,64)
//   int16 zz=(16,16)  nn=(16,32)
//   int32 zz=(8,8)    nn=(8,16)
//
// block_t<T, BH, BW> 让 C++ 类型系统区分:
//   int16_zz_t 和 int16_nn_t 是不同类型，不能混用
//   block_h / block_w 编译期可查，不用查 manifest
// ============================================================

// ============================================================
// Block Shape 注册表 — single source of truth（C++ 侧）
// Python manifest.py 的 TYPES 表应与此同步
// ============================================================

// ============================================================
// DUT Block 类型 — 256 bits (32 bytes) 一个 block
//
// C 函数的 DUT 参数用这些类型，不用裸 int16_t*
// 每个 struct 是一个 block，内含 N 个元素:
//   bint8:  32 个 int8
//   bint16: 16 个 int16
//   bint32: 8 个 int32
// ============================================================

#define DSP_BLOCK_BITS 128
#define DSP_BLOCK_BYTES (DSP_BLOCK_BITS / 8)

// golden C 头文件中的类型别名（大写，与硬件命名风格一致）
// BINT16 是裸 int16_t 的 typedef，golden C 函数用它标记参数是 block 数据
typedef int8_t  BINT8;
typedef int16_t BINT16;
typedef int32_t BINT32;

// block struct — 128 bits (16 bytes) 一个 block
//   bint8:  16 个 int8
//   bint16: 8 个 int16
//   bint32: 4 个 int32
struct bint8 {
    static constexpr int size = DSP_BLOCK_BYTES / sizeof(int8_t);  // 16
    int8_t data[DSP_BLOCK_BYTES / sizeof(int8_t)];
};

struct bint16 {
    static constexpr int size = DSP_BLOCK_BYTES / sizeof(int16_t); // 8
    int16_t data[DSP_BLOCK_BYTES / sizeof(int16_t)];
};

struct bint32 {
    static constexpr int size = DSP_BLOCK_BYTES / sizeof(int32_t); // 4
    int32_t data[DSP_BLOCK_BYTES / sizeof(int32_t)];
};
