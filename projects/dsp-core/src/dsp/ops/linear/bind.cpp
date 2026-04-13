// 绑定：matmul + linear
#include "bind_helpers.h"
#include "dsp_matrix.h"

#define BIND_MATMUL_LINEAR(DUT, dut_name)                                            \
    m.def("dsp_matmul_" #dut_name,                                                   \
        [](py::array_t<double> dst, py::array_t<double> input, py::array_t<double> weight, \
            size_t M, size_t K, size_t N) {                                          \
            auto input_dut  = to_dut<DUT>(input);                                    \
            auto weight_dut = to_dut<DUT>(weight);                                   \
            std::vector<DUT> out(num_blocks<DUT>(M * N));                             \
            dsp_matmul<DUT, DUT, DUT>(out.data(), input_dut.data(), weight_dut.data(), M, K, N); \
            from_dut(dst, out, M * N);                                               \
        });                                                                          \
    m.def("dsp_linear_" #dut_name,                                                   \
        [](py::array_t<double> dst, py::array_t<double> input, py::array_t<double> weight, \
            py::array_t<double> bias, int scale_exp, size_t M, size_t K, size_t N) { \
            auto input_dut  = to_dut<DUT>(input);                                    \
            auto weight_dut = to_dut<DUT>(weight);                                   \
            auto bias_dut   = to_dut<DUT>(bias);                                     \
            std::vector<DUT> out(num_blocks<DUT>(M * N));                             \
            dsp_linear<DUT, DUT, DUT, DUT>(out.data(), input_dut.data(), weight_dut.data(), \
                bias_dut.data(), scale_exp, M, K, N);                                \
            from_dut(dst, out, M * N);                                               \
        });

void bind_matrix(py::module& m) {
    BIND_MATMUL_LINEAR(BF8,  bf8)
    BIND_MATMUL_LINEAR(BF16, bf16)
}

#undef BIND_MATMUL_LINEAR
