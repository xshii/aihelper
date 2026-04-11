// 绑定：矩阵运算
#include "bind_helpers.h"
#include "dsp/dsp_matrix.h"

// Acc 不在函数签名中，需显式指定
template<typename Src0, typename Src1, typename Dst0, typename Acc>
void bind_gemm(py::module& m, const char* name) {
    auto fn = dsp_matmul<Src0, Src1, Dst0, Acc>;
    m.def(name, [fn](py::array_t<float> dst, py::array_t<float> src0, py::array_t<float> src1,
                      int M, int K, int N) {
        auto s0 = to_typed<Src0>(src0); auto s1 = to_typed<Src1>(src1);
        std::vector<Dst0> d(M * N);
        fn(d.data(), s0.data(), s1.data(), M, K, N);
        write_back(dst, d);
    });
}

template<typename Src0, typename Src1, typename Src2, typename Dst0, typename Acc>
void bind_linear(py::module& m, const char* name) {
    auto fn = dsp_linear<Src0, Src1, Src2, Dst0, Acc>;
    m.def(name, [fn](py::array_t<float> dst, py::array_t<float> src0, py::array_t<float> src1,
                      py::array_t<float> src2, int scale_exp, int M, int K, int N) {
        auto s0 = to_typed<Src0>(src0); auto s1 = to_typed<Src1>(src1); auto s2 = to_typed<Src2>(src2);
        std::vector<Dst0> d(M * N);
        fn(d.data(), s0.data(), s1.data(), s2.data(), scale_exp, M, K, N);
        write_back(dst, d);
    });
}

void bind_matrix(py::module& m) {
    // dsp_matmul<Src0, Src1, Dst0, Acc> — 函数名: dsp_matmul_src0_src1_dst0_acc
    bind_gemm<int16_t, int16_t, q12_22_t, Q12_22>(m, "dsp_matmul_int16_int16_q12_22_q12_22");
    bind_gemm<int16_t, int16_t, int16_t,  Q12_22>(m, "dsp_matmul_int16_int16_int16_q12_22");
    bind_gemm<int32_t, int32_t, q24_40_t, Q24_40>(m, "dsp_matmul_int32_int32_q24_40_q24_40");

    // dsp_linear<Src0, Src1, Src2, Dst0, Acc> — 函数名: dsp_linear_src0_src1_src2_dst0_acc
    bind_linear<int16_t, int16_t, int32_t, int16_t,  Q12_22>(m, "dsp_linear_int16_int16_int32_int16_q12_22");
    bind_linear<int16_t, int16_t, int32_t, q12_22_t, Q12_22>(m, "dsp_linear_int16_int16_int32_q12_22_q12_22");
    bind_linear<int32_t, int32_t, int32_t, q24_40_t, Q24_40>(m, "dsp_linear_int32_int32_int32_q24_40_q24_40");
}
