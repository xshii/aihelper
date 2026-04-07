// pybind11 绑定：把硬件团队的纯 C 函数包成 Python 可调用
//
// 编译: make build-golden
// 依赖: golden_c/include/golden_ops.h + golden_c/lib/libgolden.so

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "golden_ops.h"

namespace py = pybind11;

#define BIND_CONVERT(name) \
    m.def(#name, [](py::array_t<float> src, py::array_t<float> dst, int count) { \
        name(src.mutable_unchecked<1>().mutable_data(0), \
             dst.mutable_unchecked<1>().mutable_data(0), count); \
    })

#define BIND_UNARY(name) \
    m.def(#name, [](py::array_t<float> x, py::array_t<float> out, int count) { \
        name(x.mutable_unchecked<1>().mutable_data(0), \
             out.mutable_unchecked<1>().mutable_data(0), count); \
    })

#define BIND_ELEMENTWISE(name) \
    m.def(#name, [](py::array_t<float> a, py::array_t<float> b, py::array_t<float> out, int count) { \
        name(a.mutable_unchecked<1>().mutable_data(0), \
             b.mutable_unchecked<1>().mutable_data(0), \
             out.mutable_unchecked<1>().mutable_data(0), count); \
    })

#define BIND_GEMM(name) \
    m.def(#name, [](py::array_t<float> a, py::array_t<float> b, py::array_t<float> out, \
                     int M, int K, int N) { \
        name(a.mutable_unchecked<1>().mutable_data(0), \
             b.mutable_unchecked<1>().mutable_data(0), \
             out.mutable_unchecked<1>().mutable_data(0), M, K, N); \
    })

#define BIND_LINEAR(name) \
    m.def(#name, [](py::array_t<float> a, py::array_t<float> b, py::array_t<float> bias, \
                     py::array_t<float> out, int scale_exp, int M, int K, int N) { \
        name(a.mutable_unchecked<1>().mutable_data(0), \
             b.mutable_unchecked<1>().mutable_data(0), \
             bias.mutable_unchecked<1>().mutable_data(0), \
             out.mutable_unchecked<1>().mutable_data(0), scale_exp, M, K, N); \
    })

#define BIND_XCORR(name) \
    m.def(#name, [](py::array_t<float> a, py::array_t<float> b, py::array_t<float> out, \
                     int signal_len) { \
        name(a.mutable_unchecked<1>().mutable_data(0), \
             b.mutable_unchecked<1>().mutable_data(0), \
             out.mutable_unchecked<1>().mutable_data(0), signal_len); \
    })


PYBIND11_MODULE(_raw_bindings, m) {
    m.doc() = "Golden C bindings";

    // Convert
    BIND_CONVERT(convert_float32_to_iq16);
    BIND_CONVERT(convert_iq16_to_float32);
    BIND_CONVERT(convert_float32_to_iq32);
    BIND_CONVERT(convert_iq32_to_float32);
    BIND_CONVERT(convert_iq16_to_iq32);
    BIND_CONVERT(convert_iq32_to_iq16);

    // Matmul
    BIND_GEMM(sp_gemm_iq16_iq16_oiq32_acc_q12_22);
    BIND_GEMM(sp_gemm_iq16_iq16_oiq16_acc_q12_22);
    BIND_GEMM(sp_gemm_iq32_iq32_oiq32_acc_q24_40);

    // Fused linear
    BIND_LINEAR(sp_fused_linear_iq16_iq16_biq32_oiq16_acc_q12_22);
    BIND_LINEAR(sp_fused_linear_iq16_iq16_biq32_oiq32_acc_q12_22);
    BIND_LINEAR(sp_fused_linear_iq32_iq32_biq32_oiq32_acc_q24_40);

    // Elementwise
    BIND_ELEMENTWISE(sp_vadd_iq16);
    BIND_ELEMENTWISE(sp_vadd_iq32);
    BIND_ELEMENTWISE(sp_vmul_iq16_iq16_oiq32_acc_q12_22);

    // Unary
    BIND_UNARY(sp_abs_iq16);
    BIND_UNARY(sp_abs_iq32);

    // Correlate
    BIND_XCORR(sp_xcorr_iq16_iq16_oiq32_acc_q12_22);
    BIND_XCORR(sp_xcorr_iq32_iq32_oiq32_acc_q24_40);
}
