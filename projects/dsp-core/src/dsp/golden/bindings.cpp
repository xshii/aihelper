// pybind11 模块入口
// 各分类绑定在独立文件中：
//   bind_convert.cpp  — 类型转换 + ACC→double
//   bind_matrix.cpp   — matmul + fused linear
//   bind_vector.cpp   — add, mul, abs
//   bind_signal.cpp   — correlate
//
// 编译: make build-golden

#include <pybind11/pybind11.h>
namespace py = pybind11;

void bind_convert(py::module& m);
void bind_matrix(py::module& m);
void bind_vector(py::module& m);

PYBIND11_MODULE(_raw_bindings, m) {
    m.doc() = "Golden C bindings — manifest.py 函数名直接可调用";
    bind_convert(m);
    bind_matrix(m);
    bind_vector(m);
}
