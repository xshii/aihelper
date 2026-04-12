// 共享辅助：Python float64 numpy <-> C++ typed 的桥接
//
// to_typed<T>(arr)       — float64 numpy → vector<T>
// write_back<T>(dst, d)  — vector<T> → float64 numpy
//
// 支持的类型: double, bint8, bint16, bint32
#pragma once
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <vector>
#include "dsp/dsp_convert.h"

namespace py = pybind11;

// ============================================================
// gc_from_double — double → typed（输入转换）
// ============================================================

template<typename T> struct gc_from_double;
template<> struct gc_from_double<double> { static void call(double* d, const double* s, int n) { for(int i=0;i<n;i++) d[i]=s[i]; }};
template<> struct gc_from_double<bint8>  { static void call(bint8* d, const double* s, int n) { dsp_convert<double, bint8>(d, s, n); }};
template<> struct gc_from_double<bint16> { static void call(bint16* d, const double* s, int n) { dsp_convert<double, bint16>(d, s, n); }};
template<> struct gc_from_double<bint32> { static void call(bint32* d, const double* s, int n) { dsp_convert<double, bint32>(d, s, n); }};

template<typename T>
inline std::vector<T> to_typed(py::array_t<double> arr) {
    auto r = arr.unchecked<1>();
    int n = r.size();
    std::vector<T> buf(n);
    gc_from_double<T>::call(buf.data(), r.data(0), n);
    return buf;
}

// ============================================================
// gc_to_double — typed → double（输出转换）
// ============================================================

template<typename T> struct gc_to_double;
template<> struct gc_to_double<double> { static void call(double* d, const double* s, int n) { for(int i=0;i<n;i++) d[i]=s[i]; }};
template<> struct gc_to_double<bint8>  { static void call(double* d, const bint8* s, int n)  { dsp_convert<bint8, double>(d, s, n); }};
template<> struct gc_to_double<bint16> { static void call(double* d, const bint16* s, int n) { dsp_convert<bint16, double>(d, s, n); }};
template<> struct gc_to_double<bint32> { static void call(double* d, const bint32* s, int n) { dsp_convert<bint32, double>(d, s, n); }};

template<typename T>
inline void write_back(py::array_t<double> dst, const std::vector<T>& d, int n_elements) {
    std::vector<double> buf(n_elements);
    gc_to_double<T>::call(buf.data(), d.data(), n_elements);
    auto w = dst.mutable_unchecked<1>();
    for (int i = 0; i < n_elements; i++) w(i) = buf[i];
}

template<typename T>
inline void write_back(py::array_t<double> dst, const std::vector<T>& d) {
    write_back(dst, d, static_cast<int>(d.size()));
}

template<> inline void write_back<double>(py::array_t<double> dst, const std::vector<double>& d) {
    auto w = dst.mutable_unchecked<1>();
    for (size_t i = 0; i < d.size(); i++) w(i) = d[i];
}
