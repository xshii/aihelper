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
