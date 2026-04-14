// 绑定: transpose
//
// 对标硬件 transpose 指令 —— 物理元素搬运，shape (rows, cols) → (cols, rows)。
// C kernel 本身只在 double 域做元素重排（量化在 Python 侧的 _pre_quantize_randn_args
// 就完成了），所以不需要 to_dut / from_dut 走 round trip。
//
// bf16/bf8 两个符号都路由到同一个 dsp_transpose_double，只是为了让
// auto_register 按 dtype 建 ComputeKey(op="transpose", src0=bf16/bf8, ...)。
// Python 侧的 TransposeConvention.call_c_func 实际不会调用这些符号
// （直接走 np.swapaxes），绑定存在只是为了满足 dispatch 的 ComputeKey 查表。
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "bind_registry.h"
#include "dsp_transpose.h"

namespace py = pybind11;

#define BIND_TRANSPOSE(name)                                                     \
    m.def("dsp_transpose_" #name,                                                \
        [](py::array_t<double> dst, py::array_t<double> src,                     \
           size_t rows, size_t cols) {                                           \
            dsp_transpose_double(                                                \
                dst.mutable_data(),                                              \
                src.data(),                                                      \
                rows, cols);                                                     \
        });

void bind_transpose(py::module& m) {
    BIND_TRANSPOSE(bf8)
    BIND_TRANSPOSE(bf16)
}

#undef BIND_TRANSPOSE

REGISTER_BIND(bind_transpose)
