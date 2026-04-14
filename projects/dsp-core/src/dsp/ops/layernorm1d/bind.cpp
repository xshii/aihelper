// 绑定：layernorm1d
// C 签名: (dst, input, gamma, beta, batch, matrix, rows, cols)
//
// 内存布局 (caller 负责):
//   cols_mem = pad_dim(cols, BlockSize)
//   input / dst 形状 = (batch, matrix, rows, cols_mem), 行优先 flat
//   gamma / beta 形状 = (cols_mem,)
//
// reduction 范围:
//   每 (b,m,r) 行在前 cols 个元素上求 mean/var，[cols..cols_mem) 区不计入
#include "bind_helpers.h"
#include "bind_registry.h"
#include "dsp_vector.h"

#define BIND_LAYERNORM1D(DUT, dut_name, CT, ct_name)                                 \
    m.def("dsp_layernorm1d_" #dut_name "_" #ct_name,                                 \
        [](py::array_t<double> dst, py::array_t<double> input,                       \
            py::array_t<double> gamma, py::array_t<double> beta,                     \
            size_t batch, size_t matrix, size_t rows, size_t cols) {                 \
            auto input_dut = to_dut<DUT>(input);                                     \
            auto gamma_dut = to_dut<DUT>(gamma);                                     \
            auto beta_dut  = to_dut<DUT>(beta);                                      \
            constexpr size_t sub = subblock_size<DUT>::value;                        \
            size_t cols_mem = cols + (sub - cols % sub) % sub;                       \
            size_t total_mem = batch * matrix * rows * cols_mem;                     \
            size_t n_sub = total_mem / sub;                                          \
            std::vector<DUT> out(n_sub);                                             \
            dsp_layernorm1d<DUT, CT>(out.data(), input_dut.data(),                   \
                gamma_dut.data(), beta_dut.data(),                                   \
                batch, matrix, rows, cols);                                          \
            from_dut(dst, out, total_mem);                                           \
        });

void bind_vector(py::module& m) {
    BIND_LAYERNORM1D(BF8,  bf8,  ComputeType::INT32, int32)
    BIND_LAYERNORM1D(BF16, bf16, ComputeType::INT32, int32)
}

#undef BIND_LAYERNORM1D

REGISTER_BIND(bind_vector)
