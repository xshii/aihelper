#pragma once
#include "../include/golden_vector.h"

// template<Src0, Dst0> dsp_add(out_nd, src0_nd, src1_nd, count) — src0=src1 同类型
template<typename T>
void dsp_add(T* out_nd, const T* src0_nd, const T* src1_nd, int count);

template<> inline void dsp_add<int16_t>(int16_t* out_nd, const int16_t* src0_nd, const int16_t* src1_nd, int count)
{ sp_vadd_int16(out_nd, src0_nd, src1_nd, count); }
template<> inline void dsp_add<int32_t>(int32_t* out_nd, const int32_t* src0_nd, const int32_t* src1_nd, int count)
{ sp_vadd_int32(out_nd, src0_nd, src1_nd, count); }


// template<Src0, Src1, Dst0, Acc> dsp_mul(out_nd, src0_nd, src1_nd, count)
template<typename Src0, typename Src1, typename Dst0, typename Acc>
void dsp_mul(Dst0* out_nd, const Src0* src0_nd, const Src1* src1_nd, int count);

template<> inline void dsp_mul<int16_t, int16_t, q12_22_t, Q12_22>(
    q12_22_t* out_nd, const int16_t* src0_nd, const int16_t* src1_nd, int count)
{ sp_vmul_int16_int16_oint32_acc_q12_22(out_nd, src0_nd, src1_nd, count); }


// template<T> dsp_abs(out_nd, input_nd, count)
template<typename T>
void dsp_abs(T* out_nd, const T* input_nd, int count);

template<> inline void dsp_abs<int16_t>(int16_t* out_nd, const int16_t* input_nd, int count)
{ sp_abs_int16(out_nd, input_nd, count); }
template<> inline void dsp_abs<int32_t>(int32_t* out_nd, const int32_t* input_nd, int count)
{ sp_abs_int32(out_nd, input_nd, count); }


// template<Src0, Src1, Dst0, Acc> dsp_xcorr(out_nd, signal_nd, template_nd, signal_len)
template<typename Src0, typename Src1, typename Dst0, typename Acc>
void dsp_xcorr(Dst0* out_nd, const Src0* signal_nd, const Src1* template_nd, int signal_len);

template<> inline void dsp_xcorr<int16_t, int16_t, q12_22_t, Q12_22>(
    q12_22_t* out_nd, const int16_t* signal_nd, const int16_t* template_nd, int signal_len)
{ sp_xcorr_int16_int16_oint32_acc_q12_22(out_nd, signal_nd, template_nd, signal_len); }

template<> inline void dsp_xcorr<int32_t, int32_t, q24_40_t, Q24_40>(
    q24_40_t* out_nd, const int32_t* signal_nd, const int32_t* template_nd, int signal_len)
{ sp_xcorr_int32_int32_oint32_acc_q24_40(out_nd, signal_nd, template_nd, signal_len); }
