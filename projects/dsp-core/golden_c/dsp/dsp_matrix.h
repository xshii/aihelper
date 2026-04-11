#pragma once
#include <vector>
#include "include/golden_matrix.h"
#include "include/golden_convert.h"

#define CC(T, p) const_cast<T*>(reinterpret_cast<const T*>(p))

// ============================================================
// matmul / linear — 输出始终是 DUT block 类型
// 比数时 Python 侧调 dut_to_double 转换，不在这里做
// ============================================================

template<typename Src0, typename Src1, typename Dst0>
void dsp_matmul(Dst0* out_zz, const Src0* input_zz, const Src1* weight_nn, int M, int K, int N);

template<> inline void dsp_matmul<bint16, bint16, bint32>(
    bint32* out_zz, const bint16* input_zz, const bint16* weight_nn, int M, int K, int N) {
    std::vector<q12_22_t> acc(M * N);
    sp_gemm_int16_int16_oint32_acc_q12_22(acc.data(), CC(int16_t, input_zz), CC(int16_t, weight_nn), M, K, N);
    gc_q12_22_to_int32(reinterpret_cast<int32_t*>(out_zz), acc.data(), M * N);
}

template<> inline void dsp_matmul<bint16, bint16, bint16>(
    bint16* out_zz, const bint16* input_zz, const bint16* weight_nn, int M, int K, int N) {
    sp_gemm_int16_int16_oint16_acc_q12_22(reinterpret_cast<int16_t*>(out_zz),
        CC(int16_t, input_zz), CC(int16_t, weight_nn), M, K, N);
}

template<> inline void dsp_matmul<bint32, bint32, bint32>(
    bint32* out_zz, const bint32* input_zz, const bint32* weight_nn, int M, int K, int N) {
    std::vector<q24_40_t> acc(M * N);
    sp_gemm_int32_int32_oint32_acc_q24_40(acc.data(), CC(int32_t, input_zz), CC(int32_t, weight_nn), M, K, N);
    gc_q24_40_to_int32(reinterpret_cast<int32_t*>(out_zz), acc.data(), M * N);
}


template<typename Src0, typename Src1, typename Src2, typename Dst0>
void dsp_linear(Dst0* out_zz, const Src0* input_zz, const Src1* weight_nn,
                const Src2* bias_nd, int scale_exp, int M, int K, int N);

template<> inline void dsp_linear<bint16, bint16, int32_t, bint16>(
    bint16* out_zz, const bint16* input_zz, const bint16* weight_nn,
    const int32_t* bias_nd, int scale_exp, int M, int K, int N) {
    sp_fused_linear_int16_int16_bint32_oint16_acc_q12_22(
        reinterpret_cast<int16_t*>(out_zz), CC(int16_t, input_zz), CC(int16_t, weight_nn),
        const_cast<int32_t*>(bias_nd), scale_exp, M, K, N);
}

template<> inline void dsp_linear<bint16, bint16, int32_t, bint32>(
    bint32* out_zz, const bint16* input_zz, const bint16* weight_nn,
    const int32_t* bias_nd, int scale_exp, int M, int K, int N) {
    std::vector<q12_22_t> acc(M * N);
    sp_fused_linear_int16_int16_bint32_oint32_acc_q12_22(
        acc.data(), CC(int16_t, input_zz), CC(int16_t, weight_nn),
        const_cast<int32_t*>(bias_nd), scale_exp, M, K, N);
    gc_q12_22_to_int32(reinterpret_cast<int32_t*>(out_zz), acc.data(), M * N);
}

template<> inline void dsp_linear<bint32, bint32, int32_t, bint32>(
    bint32* out_zz, const bint32* input_zz, const bint32* weight_nn,
    const int32_t* bias_nd, int scale_exp, int M, int K, int N) {
    std::vector<q24_40_t> acc(M * N);
    sp_fused_linear_int32_int32_bint32_oint32_acc_q24_40(
        acc.data(), CC(int32_t, input_zz), CC(int32_t, weight_nn),
        const_cast<int32_t*>(bias_nd), scale_exp, M, K, N);
    gc_q24_40_to_int32(reinterpret_cast<int32_t*>(out_zz), acc.data(), M * N);
}

#undef CC
