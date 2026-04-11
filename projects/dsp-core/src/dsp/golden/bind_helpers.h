// 共享辅助：Python float64 numpy <-> C++ typed 的桥接
//
// to_typed<T>(arr)       — float64 numpy → vector<T>
// write_back<T>(dst, d)  — vector<T> → float64 numpy
//
// 支持的类型:
//   裸类型: int8_t, int16_t, int32_t, float, q12_22_t, q24_40_t
//   block 类型: bint8, bint16, bint32（256-bit block）
#pragma once
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <vector>
#include "dsp/dsp_types.h"
#include "include/golden_convert.h"

namespace py = pybind11;

// ============================================================
// gc_from_double — float32 → typed（输入转换）
// ============================================================

template<typename T> struct gc_from_double;

// 裸类型
template<> struct gc_from_double<double>   { static void call(double* d, const double* s, int n) { for(int i=0;i<n;i++) d[i]=s[i]; }};
template<> struct gc_from_double<int8_t>  { static void call(int8_t*  d, const double* s, int n) { convert_double_to_int8(d, s, n); }};
template<> struct gc_from_double<int16_t> { static void call(int16_t* d, const double* s, int n) { convert_double_to_int16(d, s, n); }};
template<> struct gc_from_double<int32_t> { static void call(int32_t* d, const double* s, int n) { convert_double_to_int32(d, s, n); }};

// Block 类型 — float 逐元素转 DUT 后填入 block.data
template<> struct gc_from_double<bint8> {
    static void call(bint8* d, const double* s, int n) {
        convert_double_to_int8(reinterpret_cast<int8_t*>(d), s, n);
    }
};
template<> struct gc_from_double<bint16> {
    static void call(bint16* d, const double* s, int n) {
        convert_double_to_int16(reinterpret_cast<int16_t*>(d), s, n);
    }
};
template<> struct gc_from_double<bint32> {
    static void call(bint32* d, const double* s, int n) {
        convert_double_to_int32(reinterpret_cast<int32_t*>(d), s, n);
    }
};

// to_typed: float numpy → vector<T>
template<typename T>
inline std::vector<T> to_typed(py::array_t<double> arr) {
    auto r = arr.unchecked<1>();
    int n = r.size();
    std::vector<T> buf(n);
    gc_from_double<T>::call(buf.data(), r.data(0), n);
    return buf;
}

// ============================================================
// gc_to_double — typed → float32（输出转换）
// ============================================================

template<typename T> struct gc_to_double;

// 裸类型
template<> struct gc_to_double<int8_t>    { static void call(double* d, const int8_t*    s, int n) { convert_int8_to_double(d, s, n); }};
template<> struct gc_to_double<int16_t>   { static void call(double* d, const int16_t*   s, int n) { convert_int16_to_double(d, s, n); }};
template<> struct gc_to_double<int32_t>   { static void call(double* d, const int32_t*   s, int n) { convert_int32_to_double(d, s, n); }};



// Block 类型 — block.data 逐元素转 float
template<> struct gc_to_double<bint8> {
    static void call(double* d, const bint8* s, int n) {
        convert_int8_to_double(d, reinterpret_cast<const int8_t*>(s), n);
    }
};
template<> struct gc_to_double<bint16> {
    static void call(double* d, const bint16* s, int n) {
        convert_int16_to_double(d, reinterpret_cast<const int16_t*>(s), n);
    }
};
template<> struct gc_to_double<bint32> {
    static void call(double* d, const bint32* s, int n) {
        convert_int32_to_double(d, reinterpret_cast<const int32_t*>(s), n);
    }
};

// double identity
template<> struct gc_to_double<double> { static void call(double* d, const double* s, int n) { for(int i=0;i<n;i++) d[i]=s[i]; }};

// write_back: vector<T> → float numpy
template<typename T>
inline void write_back(py::array_t<double> dst, const std::vector<T>& d, int n_elements) {
    std::vector<double> buf(n_elements);
    gc_to_double<T>::call(buf.data(), d.data(), n_elements);
    auto w = dst.mutable_unchecked<1>();
    for (int i = 0; i < n_elements; i++) w(i) = buf[i];
}

// 裸类型: d.size() == n_elements
template<typename T>
inline void write_back(py::array_t<double> dst, const std::vector<T>& d) {
    write_back(dst, d, static_cast<int>(d.size()));
}

template<> inline void write_back<double>(py::array_t<double> dst, const std::vector<double>& d) {
    auto w = dst.mutable_unchecked<1>();
    for (size_t i = 0; i < d.size(); i++) w(i) = d[i];
}
