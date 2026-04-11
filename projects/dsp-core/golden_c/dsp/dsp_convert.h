#pragma once
#include "../include/golden_convert.h"

// template<Src, Dst> dsp_convert(dst, src, count)
template<typename Src, typename Dst>
void dsp_convert(Dst* dst, const Src* src, int count);

// float32 → DUT
template<> inline void dsp_convert<float, int8_t>(int8_t* dst, const float* src, int count)
{ convert_float32_to_int8(dst, src, count); }
template<> inline void dsp_convert<float, int16_t>(int16_t* dst, const float* src, int count)
{ convert_float32_to_int16(dst, src, count); }
template<> inline void dsp_convert<float, int32_t>(int32_t* dst, const float* src, int count)
{ convert_float32_to_int32(dst, src, count); }

// DUT → float32
template<> inline void dsp_convert<int8_t, float>(float* dst, const int8_t* src, int count)
{ convert_int8_to_float32(dst, src, count); }
template<> inline void dsp_convert<int16_t, float>(float* dst, const int16_t* src, int count)
{ convert_int16_to_float32(dst, src, count); }
template<> inline void dsp_convert<int32_t, float>(float* dst, const int32_t* src, int count)
{ convert_int32_to_float32(dst, src, count); }

// DUT → DUT
template<> inline void dsp_convert<int8_t, int16_t>(int16_t* dst, const int8_t* src, int count)
{ convert_int8_to_int16(dst, src, count); }
template<> inline void dsp_convert<int16_t, int8_t>(int8_t* dst, const int16_t* src, int count)
{ convert_int16_to_int8(dst, src, count); }
template<> inline void dsp_convert<int16_t, int32_t>(int32_t* dst, const int16_t* src, int count)
{ convert_int16_to_int32(dst, src, count); }
template<> inline void dsp_convert<int32_t, int16_t>(int16_t* dst, const int32_t* src, int count)
{ convert_int32_to_int16(dst, src, count); }

// ACC → float32
template<> inline void dsp_convert<q12_22_t, float>(float* dst, const q12_22_t* src, int count)
{ convert_q12_22_to_float32(dst, src, count); }
template<> inline void dsp_convert<q24_40_t, float>(float* dst, const q24_40_t* src, int count)
{ convert_q24_40_to_float32(dst, src, count); }
