#pragma once
#include <vector>
#include "include/golden_matrix.h"
#include "dsp/dsp_convert.h"

template<typename Src0, typename Src1, typename Dst0>
void dsp_matmul(Dst0* out_zz, const Src0* input_zz, const Src1* weight_nn, int M, int K, int N);

template<> inline void dsp_matmul<bint16, bint16, bint32>(
    bint32* out_zz, const bint16* input_zz, const bint16* weight_nn, int M, int K, int N) {
    std::vector<Q12_22> acc(M * N);
    sp_gemm_int16_int16_oint32_acc_q12_22(acc.data(), input_zz, weight_nn, M, K, N);
    for (int i = 0; i < M * N; i += BINT32_SIZE)
        acc_q12_22_to_bint32(&acc[i], &out_zz[i / BINT32_SIZE]);
}

template<> inline void dsp_matmul<bint16, bint16, bint16>(
    bint16* out_zz, const bint16* input_zz, const bint16* weight_nn, int M, int K, int N) {
    sp_gemm_int16_int16_oint16_acc_q12_22(out_zz, input_zz, weight_nn, M, K, N);
}

template<> inline void dsp_matmul<bint32, bint32, bint32>(
    bint32* out_zz, const bint32* input_zz, const bint32* weight_nn, int M, int K, int N) {
    std::vector<Q24_40> acc(M * N);
    sp_gemm_int32_int32_oint32_acc_q24_40(acc.data(), input_zz, weight_nn, M, K, N);
    for (int i = 0; i < M * N; i += BINT32_SIZE)
        acc_q24_40_to_bint32(&acc[i], &out_zz[i / BINT32_SIZE]);
}

template<typename Src0, typename Src1, typename Src2, typename Dst0>
void dsp_linear(Dst0* out_zz, const Src0* input_zz, const Src1* weight_nn,
                const Src2* bias_nd, int scale_exp, int M, int K, int N);

template<> inline void dsp_linear<bint16, bint16, bint32, bint16>(
    bint16* out_zz, const bint16* input_zz, const bint16* weight_nn,
    const bint32* bias_nd, int scale_exp, int M, int K, int N) {
    sp_fused_linear_int16_int16_bint32_oint16_acc_q12_22(
        out_zz, input_zz, weight_nn, bias_nd, scale_exp, M, K, N);
}

template<> inline void dsp_linear<bint16, bint16, bint32, bint32>(
    bint32* out_zz, const bint16* input_zz, const bint16* weight_nn,
    const bint32* bias_nd, int scale_exp, int M, int K, int N) {
    std::vector<Q12_22> acc(M * N);
    sp_fused_linear_int16_int16_bint32_oint32_acc_q12_22(
        acc.data(), input_zz, weight_nn, bias_nd, scale_exp, M, K, N);
    for (int i = 0; i < M * N; i += BINT32_SIZE)
        acc_q12_22_to_bint32(&acc[i], &out_zz[i / BINT32_SIZE]);
}

template<> inline void dsp_linear<bint32, bint32, bint32, bint32>(
    bint32* out_zz, const bint32* input_zz, const bint32* weight_nn,
    const bint32* bias_nd, int scale_exp, int M, int K, int N) {
    std::vector<Q24_40> acc(M * N);
    sp_fused_linear_int32_int32_bint32_oint32_acc_q24_40(
        acc.data(), input_zz, weight_nn, bias_nd, scale_exp, M, K, N);
    for (int i = 0; i < M * N; i += BINT32_SIZE)
        acc_q24_40_to_bint32(&acc[i], &out_zz[i / BINT32_SIZE]);
}
