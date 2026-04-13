#pragma once
#include <cassert>
#include "golden_convert.h"

// ============================================================
// dsp_convert<Dst, Src>(dst, src, count)
// 统一类型转换接口，按 subblock 循环调用硬件接口
// count = 总 Src 元素数（不是 subblock 数）
//
// 支持的转换方向：
//   double ↔ DUT    (BF8, BF16)
//   ACC   ↔ DUT    (Q12_22 ↔ BF8/BF16)
//   double → double (identity)
// ============================================================

template<typename Dst, typename Src>
void dsp_convert(Dst* dst, Src* src, size_t count);

#pragma region DOUBLE<->DUT

#define DSP_CONVERT_DUT(DUT, BlockSize, ToDut, FromDut)                               \
template<> inline void dsp_convert<DUT, double>(DUT* dst, double* src, size_t count) {  \
    assert(count % BlockSize == 0);                                                  \
    for (size_t i = 0; i < count; i += BlockSize)                              \
        dst[i / BlockSize] = ToDut(src + i);                                         \
}                                                                                    \
template<> inline void dsp_convert<double, DUT>(double* dst, DUT* src, size_t count) {  \
    assert(count % BlockSize == 0);                                                  \
    for (size_t i = 0; i < count; i += BlockSize)                              \
        FromDut(src[i / BlockSize], dst + i);                                        \
}

DSP_CONVERT_DUT(BF8,  BF8_BLOCK_SIZE,  DoubleToBF8,  BF8ToDouble)
DSP_CONVERT_DUT(BF16, BF16_BLOCK_SIZE, DoubleToBF16, BF16ToDouble)

#undef DSP_CONVERT_DUT

#pragma endregion

#pragma region ACC<->DUT

#define DSP_CONVERT_ACC(DUT, ACC, BlockSize, AccToDut, DutToAcc)                     \
template<> inline void dsp_convert<DUT, ACC>(DUT* dst, ACC* src, size_t count) {  \
    assert(count % BlockSize == 0);                                                  \
    for (size_t i = 0; i < count; i += BlockSize)                              \
        AccToDut(src + i, &dst[i / BlockSize]);                                      \
}                                                                                    \
template<> inline void dsp_convert<ACC, DUT>(ACC* dst, DUT* src, size_t count) {  \
    assert(count % BlockSize == 0);                                                  \
    for (size_t i = 0; i < count; i += BlockSize)                              \
        DutToAcc(&src[i / BlockSize], dst + i);                                      \
}

DSP_CONVERT_ACC(BF8,  Q12_22, BF8_BLOCK_SIZE,  acc_q12_22_to_bf8,  bf8_to_acc_q12_22)
DSP_CONVERT_ACC(BF16, Q12_22, BF16_BLOCK_SIZE, acc_q12_22_to_bf16, bf16_to_acc_q12_22)

#undef DSP_CONVERT_ACC

#pragma endregion

#pragma region IDENTITY

template<> inline void dsp_convert<double, double>(double* dst, double* src, size_t count) {
    for (size_t i = 0; i < count; i++) dst[i] = src[i];
}

#pragma endregion
