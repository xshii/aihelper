// pybind11 模块入口
//
// 每个 op 的 bind.cpp 用 REGISTER_BIND(bind_xxx) 把自己的注册函数
// 塞进全局 registry，这里一次遍历即可。新增 op 时不需要改本文件。
#include <pybind11/pybind11.h>
#include "bind_registry.h"

namespace py = pybind11;

PYBIND11_MODULE(_raw_bindings, m) {
    m.doc() = "Golden C bindings — manifest.py 函数名直接可调用";
    for (auto& fn : bind_registry()) {
        fn(m);
    }
}
