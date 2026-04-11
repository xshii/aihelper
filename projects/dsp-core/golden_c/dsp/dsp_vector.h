#pragma once
#include <vector>
#include "include/golden_vector.h"
#include "include/golden_convert.h"

#define CC(T, p) const_cast<T*>(reinterpret_cast<const T*>(p))

// --- add ---
template<typename T>
void dsp_add(T* out_nd, const T* src0_nd, const T* src1_nd, int count);

template<> inline void dsp_add<bint16>(bint16* out_nd, const bint16* src0_nd, const bint16* src1_nd, int count)
{ sp_vadd_int16(reinterpret_cast<int16_t*>(out_nd), CC(int16_t, src0_nd), CC(int16_t, src1_nd), count); }

template<> inline void dsp_add<bint32>(bint32* out_nd, const bint32* src0_nd, const bint32* src1_nd, int count)
{ sp_vadd_int32(reinterpret_cast<int32_t*>(out_nd), CC(int32_t, src0_nd), CC(int32_t, src1_nd), count); }

// --- mul ---
template<typename Src0, typename Src1, typename Dst0>
void dsp_mul(Dst0* out_nd, const Src0* src0_nd, const Src1* src1_nd, int count);

template<> inline void dsp_mul<bint16, bint16, bint32>(
    bint32* out_nd, const bint16* src0_nd, const bint16* src1_nd, int count) {
    std::vector<q12_22_t> acc(count);
    sp_vmul_int16_int16_oint32_acc_q12_22(acc.data(), CC(int16_t, src0_nd), CC(int16_t, src1_nd), count);
    gc_q12_22_to_int32(reinterpret_cast<int32_t*>(out_nd), acc.data(), count);
}

// --- abs ---
template<typename T>
void dsp_abs(T* out_nd, const T* input_nd, int count);

template<> inline void dsp_abs<bint16>(bint16* out_nd, const bint16* input_nd, int count)
{ sp_abs_int16(reinterpret_cast<int16_t*>(out_nd), CC(int16_t, input_nd), count); }

template<> inline void dsp_abs<bint32>(bint32* out_nd, const bint32* input_nd, int count)
{ sp_abs_int32(reinterpret_cast<int32_t*>(out_nd), CC(int32_t, input_nd), count); }

// --- correlate ---
template<typename Src0, typename Src1, typename Dst0>
void dsp_xcorr(Dst0* out_nd, const Src0* signal_nd, const Src1* template_nd, int signal_len);

template<> inline void dsp_xcorr<bint16, bint16, bint32>(
    bint32* out_nd, const bint16* signal_nd, const bint16* template_nd, int signal_len) {
    std::vector<q12_22_t> acc(signal_len);
    sp_xcorr_int16_int16_oint32_acc_q12_22(acc.data(), CC(int16_t, signal_nd), CC(int16_t, template_nd), signal_len);
    gc_q12_22_to_int32(reinterpret_cast<int32_t*>(out_nd), acc.data(), signal_len);
}

template<> inline void dsp_xcorr<bint32, bint32, bint32>(
    bint32* out_nd, const bint32* signal_nd, const bint32* template_nd, int signal_len) {
    std::vector<q24_40_t> acc(signal_len);
    sp_xcorr_int32_int32_oint32_acc_q24_40(acc.data(), CC(int32_t, signal_nd), CC(int32_t, template_nd), signal_len);
    gc_q24_40_to_int32(reinterpret_cast<int32_t*>(out_nd), acc.data(), signal_len);
}

// ============================================================
// 需要指定计算精度的算子 — 加 ComputeType 模板参数
// Python 函数名最后一段体现: dsp_layernorm_bint16_bint16_fp32
// ============================================================

// --- layernorm（框架预留，待硬件实现）---
template<typename Src, typename Dst, typename ComputeType>
void dsp_layernorm(Dst* out_nd, const Src* input_nd, int N, float eps);

// 占位: int16 输入，int16 输出，fp32 计算精度
// template<> inline void dsp_layernorm<bint16, bint16, float>(...) { ... }

#undef CC
