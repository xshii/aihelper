#pragma once
#include <vector>
#include "golden_matrix.h"
#include "dsp_convert.h"

// input (ZZ) + weight (NN) 可以是不同 DUT 类型；bias 和 output 都跟 input 同类型。
template<typename Src0, typename Src1, typename Dst0>
void dsp_matmul(Dst0* out_zz, Src0* input_zz, Src1* weight_nn,
                size_t M, size_t K, size_t N);

template<typename Src0, typename Src1, typename Src2, typename Dst0>
void dsp_linear(Dst0* out_zz, Src0* input_zz, Src1* weight_nn,
                Src2* bias_nd, int scale_exp, size_t M, size_t K, size_t N);

#pragma region MATMUL_LINEAR

// 统一形式: (DUT_A, DUT_W) 两参数，同构就 DUT_A == DUT_W。
// 特化: dsp_matmul<DUT_A, DUT_W, DUT_A>,  dsp_linear<DUT_A, DUT_W, DUT_A, DUT_A>
#define DSP_MATMUL_LINEAR(DUT_A, DUT_W, ACC, GemmFn)                                 \
template<> inline void dsp_matmul<DUT_A, DUT_W, DUT_A>(                              \
    DUT_A* out_zz, DUT_A* input_zz, DUT_W* weight_nn,                                \
    size_t M, size_t K, size_t N) {                                                  \
    std::vector<ACC> acc(M * N);                                                     \
    GemmFn(acc.data(), input_zz, weight_nn, nullptr, 0, M, K, N);                    \
    dsp_convert<DUT_A, ACC>(out_zz, acc.data(), M * N);                              \
}                                                                                    \
template<> inline void dsp_linear<DUT_A, DUT_W, DUT_A, DUT_A>(                       \
    DUT_A* out_zz, DUT_A* input_zz, DUT_W* weight_nn,                                \
    DUT_A* bias_nd, int scale_exp, size_t M, size_t K, size_t N) {                   \
    std::vector<ACC> acc(M * N);                                                     \
    GemmFn(acc.data(), input_zz, weight_nn, bias_nd, scale_exp, M, K, N);            \
    dsp_convert<DUT_A, ACC>(out_zz, acc.data(), M * N);                              \
}

DSP_MATMUL_LINEAR(BF8,  BF8,  Q12_22, sp_gemm_bf8_dutw_bf8_acc_q12_22)
DSP_MATMUL_LINEAR(BF16, BF16, Q12_22, sp_gemm_bf16_dutw_bf16_acc_q12_22)
DSP_MATMUL_LINEAR(BF16, BF8,  Q12_22, sp_gemm_bf16_dutw_bf8_acc_q12_22)

#undef DSP_MATMUL_LINEAR

#pragma endregion
