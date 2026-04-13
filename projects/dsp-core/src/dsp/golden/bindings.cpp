// pybind11 模块入口
// 各 op 绑定在对应目录下:
//   ops/_convert/bind.cpp  — 类型转换
//   ops/linear/bind.cpp    — matmul + linear
//   ops/layernorm/bind.cpp — layernorm
//
// 新增 op: 在 ops/<op_name>/ 下加 bind.cpp，CMake 自动收集。
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
