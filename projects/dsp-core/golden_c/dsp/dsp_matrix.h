#pragma once
#include "../include/golden_matrix.h"

// template<Src0, Src1, Dst0, Acc> dsp_matmul(out_zz, input_zz, weight_nn, M, K, N)
template<typename Src0, typename Src1, typename Dst0, typename Acc>
void dsp_matmul(Dst0* out_zz, const Src0* input_zz, const Src1* weight_nn, int M, int K, int N);

template<> inline void dsp_matmul<int16_t, int16_t, q12_22_t, Q12_22>(
    q12_22_t* out_zz, const int16_t* input_zz, const int16_t* weight_nn, int M, int K, int N)
{ sp_gemm_int16_int16_oint32_acc_q12_22(out_zz, input_zz, weight_nn, M, K, N); }

template<> inline void dsp_matmul<int16_t, int16_t, int16_t, Q12_22>(
    int16_t* out_zz, const int16_t* input_zz, const int16_t* weight_nn, int M, int K, int N)
{ sp_gemm_int16_int16_oint16_acc_q12_22(out_zz, input_zz, weight_nn, M, K, N); }

template<> inline void dsp_matmul<int32_t, int32_t, q24_40_t, Q24_40>(
    q24_40_t* out_zz, const int32_t* input_zz, const int32_t* weight_nn, int M, int K, int N)
{ sp_gemm_int32_int32_oint32_acc_q24_40(out_zz, input_zz, weight_nn, M, K, N); }


// template<Src0, Src1, Src2, Dst0, Acc> dsp_linear(out_zz, input_zz, weight_nn, bias_nd, scale_exp, M, K, N)
template<typename Src0, typename Src1, typename Src2, typename Dst0, typename Acc>
void dsp_linear(Dst0* out_zz, const Src0* input_zz, const Src1* weight_nn,
                const Src2* bias_nd, int scale_exp, int M, int K, int N);

template<> inline void dsp_linear<int16_t, int16_t, int32_t, int16_t, Q12_22>(
    int16_t* out_zz, const int16_t* input_zz, const int16_t* weight_nn,
    const int32_t* bias_nd, int scale_exp, int M, int K, int N)
{ sp_fused_linear_int16_int16_bint32_oint16_acc_q12_22(out_zz, input_zz, weight_nn, bias_nd, scale_exp, M, K, N); }

template<> inline void dsp_linear<int16_t, int16_t, int32_t, q12_22_t, Q12_22>(
    q12_22_t* out_zz, const int16_t* input_zz, const int16_t* weight_nn,
    const int32_t* bias_nd, int scale_exp, int M, int K, int N)
{ sp_fused_linear_int16_int16_bint32_oint32_acc_q12_22(out_zz, input_zz, weight_nn, bias_nd, scale_exp, M, K, N); }

template<> inline void dsp_linear<int32_t, int32_t, int32_t, q24_40_t, Q24_40>(
    q24_40_t* out_zz, const int32_t* input_zz, const int32_t* weight_nn,
    const int32_t* bias_nd, int scale_exp, int M, int K, int N)
{ sp_fused_linear_int32_int32_bint32_oint32_acc_q24_40(out_zz, input_zz, weight_nn, bias_nd, scale_exp, M, K, N); }
