#pragma once
#include <vector>
#include "include/golden_vector.h"
#include "dsp/dsp_convert.h"

template<typename T>
void dsp_add(T* out_nd, const T* src0_nd, const T* src1_nd, int count);

template<> inline void dsp_add<bint16>(bint16* out, const bint16* s0, const bint16* s1, int count)
{ sp_vadd_int16(out, s0, s1, count); }
template<> inline void dsp_add<bint32>(bint32* out, const bint32* s0, const bint32* s1, int count)
{ sp_vadd_int32(out, s0, s1, count); }

template<typename Src0, typename Src1, typename Dst0>
void dsp_mul(Dst0* out, const Src0* s0, const Src1* s1, int count);

template<> inline void dsp_mul<bint16, bint16, bint32>(
    bint32* out, const bint16* s0, const bint16* s1, int count) {
    std::vector<Q12_22> acc(count);
    sp_vmul_int16_int16_oint32_acc_q12_22(acc.data(), s0, s1, count);
    for (int i = 0; i < count; i += BINT32_SIZE)
        acc_q12_22_to_bint32(&acc[i], &out[i / BINT32_SIZE]);
}

template<typename T>
void dsp_abs(T* out, const T* input, int count);

template<> inline void dsp_abs<bint16>(bint16* out, const bint16* input, int count)
{ sp_abs_int16(out, input, count); }
template<> inline void dsp_abs<bint32>(bint32* out, const bint32* input, int count)
{ sp_abs_int32(out, input, count); }

template<typename Src0, typename Src1, typename Dst0>
void dsp_xcorr(Dst0* out, const Src0* signal, const Src1* templ, int signal_len);

template<> inline void dsp_xcorr<bint16, bint16, bint32>(
    bint32* out, const bint16* signal, const bint16* templ, int signal_len) {
    std::vector<Q12_22> acc(signal_len);
    sp_xcorr_int16_int16_oint32_acc_q12_22(acc.data(), signal, templ, signal_len);
    for (int i = 0; i < signal_len; i += BINT32_SIZE)
        acc_q12_22_to_bint32(&acc[i], &out[i / BINT32_SIZE]);
}

template<> inline void dsp_xcorr<bint32, bint32, bint32>(
    bint32* out, const bint32* signal, const bint32* templ, int signal_len) {
    std::vector<Q24_40> acc(signal_len);
    sp_xcorr_int32_int32_oint32_acc_q24_40(acc.data(), signal, templ, signal_len);
    for (int i = 0; i < signal_len; i += BINT32_SIZE)
        acc_q24_40_to_bint32(&acc[i], &out[i / BINT32_SIZE]);
}
