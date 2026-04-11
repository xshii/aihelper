// 共享辅助：Python float32 numpy ↔ C++ typed int 的桥接
//
// 为什么需要：
//   Python 侧统一用 float32 numpy 传输数据（dispatch.py 转的），
//   但 dsp_*.h 的 C 函数要求真实类型（int16_t*, int32_t*, q12_22_t*）。
//   这两个模板在中间做类型转换，通过 trait 自动选对应的 golden C convert 函数。
//
// to_typed<T>(arr)       — 输入转换：调 golden C 的 convert_float32_to_* 函数
// write_back<T>(dst, d)  — 输出转换：C 函数输出的 ACC 值回写到 float32 numpy
//
// 注意：本层只做类型转换，不做 block padding/unpadding。
//   当前 demo 的 C 函数直接操作原始 shape（如 [14,12]），不需要 padding。
//   真实硬件接入时，C 函数操作 block 对齐后的数据（如 [16,16]），
//   padding/unpadding 应在 convention 层或 dispatch 层处理（调 C 前 pad，调完 unpad）。
#pragma once
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <vector>
#include "dsp/dsp_types.h"
#include "include/golden_convert.h"

namespace py = pybind11;

// --- 输入转换：float32 numpy → typed buffer（通过 golden C convert 函数）---
// gc_from_float32 trait: 按类型选对应的 golden C 转换函数

template<typename T> struct gc_from_float32;
template<> struct gc_from_float32<float>   { static void call(float*   d, const float* s, int n) { for(int i=0;i<n;i++) d[i]=s[i]; }};
template<> struct gc_from_float32<int8_t>  { static void call(int8_t*  d, const float* s, int n) { convert_float32_to_int8(d, s, n); }};
template<> struct gc_from_float32<int16_t> { static void call(int16_t* d, const float* s, int n) { convert_float32_to_int16(d, s, n); }};
template<> struct gc_from_float32<int32_t> { static void call(int32_t* d, const float* s, int n) { convert_float32_to_int32(d, s, n); }};
// ACC 类型: float32 → int32 → 填入 .raw
template<> struct gc_from_float32<q12_22_t> {
    static void call(q12_22_t* d, const float* s, int n) {
        std::vector<int32_t> tmp(n); convert_float32_to_int32(tmp.data(), s, n);
        for (int i = 0; i < n; i++) d[i].raw = tmp[i];
    }
};
template<> struct gc_from_float32<q24_40_t> {
    static void call(q24_40_t* d, const float* s, int n) {
        std::vector<int32_t> tmp(n); convert_float32_to_int32(tmp.data(), s, n);
        for (int i = 0; i < n; i++) d[i].raw = tmp[i];
    }
};

template<typename T>
inline std::vector<T> to_typed(py::array_t<float> arr) {
    auto r = arr.unchecked<1>();
    std::vector<T> buf(r.size());
    gc_from_float32<T>::call(buf.data(), r.data(0), r.size());
    return buf;
}

// --- 输出转换：C 函数输出 → float32 numpy（通过 golden C convert 函数）---
// gc_to_float32 trait: 按类型选对应的 golden C 转换函数

template<typename T> struct gc_to_float32;
// DUT 类型
template<> struct gc_to_float32<int8_t>    { static void call(float* d, const int8_t*    s, int n) { convert_int8_to_float32(d, s, n); }};
template<> struct gc_to_float32<int16_t>   { static void call(float* d, const int16_t*   s, int n) { convert_int16_to_float32(d, s, n); }};
template<> struct gc_to_float32<int32_t>   { static void call(float* d, const int32_t*   s, int n) { convert_int32_to_float32(d, s, n); }};
// ACC 类型（底层 int32，但用 Q 格式解码）
template<> struct gc_to_float32<q12_22_t> { static void call(float* d, const q12_22_t* s, int n) { convert_q12_22_to_float32(d, s, n); }};
template<> struct gc_to_float32<q24_40_t> { static void call(float* d, const q24_40_t* s, int n) { convert_q24_40_to_float32(d, s, n); }};

template<typename T>
inline void write_back(py::array_t<float> dst, const std::vector<T>& d) {
    std::vector<float> buf(d.size());
    gc_to_float32<T>::call(buf.data(), d.data(), d.size());
    auto w = dst.mutable_unchecked<1>();
    for (size_t i = 0; i < d.size(); i++) w(i) = buf[i];
}

template<> inline void write_back<float>(py::array_t<float> dst, const std::vector<float>& d) {
    auto w = dst.mutable_unchecked<1>();
    for (size_t i = 0; i < d.size(); i++) w(i) = d[i];
}

