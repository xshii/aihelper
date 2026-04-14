// 自注册 binding 的全局注册表
//
// 用法: 在每个 op 的 bind.cpp 文件末尾写一行
//   REGISTER_BIND(bind_my_op)
//
// PYBIND11_MODULE 入口一次性遍历 bind_registry() 调用所有已注册的 bind 函数。
// 新增 op 时只需加 bind.cpp + REGISTER_BIND(...)，不需要改 bindings.cpp。
#pragma once

#include <pybind11/pybind11.h>
#include <functional>
#include <vector>

using BindFn = std::function<void(pybind11::module&)>;

inline std::vector<BindFn>& bind_registry() {
    static std::vector<BindFn> reg;
    return reg;
}

struct _BindRegistrar {
    _BindRegistrar(BindFn fn) { bind_registry().push_back(std::move(fn)); }
};

#define REGISTER_BIND(FN)                                                    \
    namespace {                                                               \
    static _BindRegistrar _bind_reg_##FN([](pybind11::module& m) { FN(m); }); \
    }
