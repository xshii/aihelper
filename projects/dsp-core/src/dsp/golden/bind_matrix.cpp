// 绑定：矩阵运算 — 输出 DUT block，比数由 Python 侧 dut_to_double 处理
#include "bind_helpers.h"
#include "dsp/dsp_matrix.h"

template<typename Src0, typename Src1, typename Dst0>
void bind_gemm(py::module& m, const char* name) {
    m.def(name, [](py::array_t<double> dst, py::array_t<double> src0, py::array_t<double> src1,
                    int M, int K, int N) {
        auto s0 = to_typed<Src0>(src0); auto s1 = to_typed<Src1>(src1);
        std::vector<Dst0> d(num_blocks<Dst0>(M * N));
        dsp_matmul<Src0, Src1, Dst0>(d.data(), s0.data(), s1.data(), M, K, N);
        write_back(dst, d, M * N);
    });
}

template<typename Src0, typename Src1, typename Src2, typename Dst0>
void bind_linear(py::module& m, const char* name) {
    m.def(name, [](py::array_t<double> dst, py::array_t<double> src0, py::array_t<double> src1,
                    py::array_t<double> src2, int scale_exp, int M, int K, int N) {
        auto s0 = to_typed<Src0>(src0); auto s1 = to_typed<Src1>(src1); auto s2 = to_typed<Src2>(src2);
        std::vector<Dst0> d(num_blocks<Dst0>(M * N));
        dsp_linear<Src0, Src1, Src2, Dst0>(d.data(), s0.data(), s1.data(), s2.data(), scale_exp, M, K, N);
        write_back(dst, d, M * N);
    });
}

void bind_matrix(py::module& m) {
    bind_gemm<bint16, bint16, bint32>(m, "dsp_matmul_bint16_bint16_bint32");
    bind_gemm<bint16, bint16, bint16>(m, "dsp_matmul_bint16_bint16_bint16");
    bind_gemm<bint32, bint32, bint32>(m, "dsp_matmul_bint32_bint32_bint32");

    bind_linear<bint16, bint16, bint32, bint16>(m, "dsp_linear_bint16_bint16_bint32_bint16");
    bind_linear<bint16, bint16, bint32, bint32>(m, "dsp_linear_bint16_bint16_bint32_bint32");
    bind_linear<bint32, bint32, bint32, bint32>(m, "dsp_linear_bint32_bint32_bint32_bint32");
}
