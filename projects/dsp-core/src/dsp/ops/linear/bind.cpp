// 绑定：matmul + linear
// 统一形式 dsp_matmul_<dut_a>_dutw_<dut_w>，同构就 dut_a == dut_w。
#include "bind_helpers.h"
#include "dsp_matrix.h"

#define BIND_MATMUL_LINEAR(DUT_A, a_name, DUT_W, w_name)                             \
    m.def("dsp_matmul_" #a_name "_dutw_" #w_name,                                    \
        [](py::array_t<double> dst, py::array_t<double> input,                       \
           py::array_t<double> weight, size_t M, size_t K, size_t N) {               \
            auto input_dut  = to_dut<DUT_A>(input);                                  \
            auto weight_dut = to_dut<DUT_W>(weight);                                 \
            std::vector<DUT_A> out(num_blocks<DUT_A>(M * N));                        \
            dsp_matmul<DUT_A, DUT_W, DUT_A>(out.data(),                              \
                input_dut.data(), weight_dut.data(), M, K, N);                       \
            from_dut(dst, out, M * N);                                               \
        });                                                                          \
    m.def("dsp_linear_" #a_name "_dutw_" #w_name,                                    \
        [](py::array_t<double> dst, py::array_t<double> input,                       \
           py::array_t<double> weight, py::array_t<double> bias,                     \
           int scale_exp, size_t M, size_t K, size_t N) {                            \
            auto input_dut  = to_dut<DUT_A>(input);                                  \
            auto weight_dut = to_dut<DUT_W>(weight);                                 \
            auto bias_dut   = to_dut<DUT_A>(bias);                                   \
            std::vector<DUT_A> out(num_blocks<DUT_A>(M * N));                        \
            dsp_linear<DUT_A, DUT_W, DUT_A, DUT_A>(out.data(),                       \
                input_dut.data(), weight_dut.data(),                                 \
                bias_dut.data(), scale_exp, M, K, N);                                \
            from_dut(dst, out, M * N);                                               \
        });

void bind_matrix(py::module& m) {
    BIND_MATMUL_LINEAR(BF8,  bf8,  BF8, bf8)
    BIND_MATMUL_LINEAR(BF16, bf16, BF16, bf16)
    BIND_MATMUL_LINEAR(BF16, bf16, BF8, bf8)
}

#undef BIND_MATMUL_LINEAR
