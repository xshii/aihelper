// 共享辅助：Python float64 numpy <-> C++ bint block 的桥接
#pragma once
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <vector>
#include "dsp/dsp_convert.h"

namespace py = pybind11;

// subblock 元素数（从 dsp_convert.h 的常量取）
template<typename T> struct subblock_size { static constexpr int value = 1; };
template<> struct subblock_size<bint8>  { static constexpr int value = BINT8_SIZE; };
template<> struct subblock_size<bint16> { static constexpr int value = BINT16_SIZE; };
template<> struct subblock_size<bint32> { static constexpr int value = BINT32_SIZE; };

// 按 subblock 数向上取整
template<typename T>
inline int num_blocks(int n_elements) {
    int sz = subblock_size<T>::value;
    return (n_elements + sz - 1) / sz;
}

// double numpy → vector<T>
template<typename T>
inline std::vector<T> to_typed(py::array_t<double> arr) {
    auto r = arr.unchecked<1>();
    int n = r.size();
    std::vector<T> buf(num_blocks<T>(n));
    dsp_convert<double, T>(buf.data(), r.data(0), n);
    return buf;
}

// double 特化: 直接拷贝
template<>
inline std::vector<double> to_typed<double>(py::array_t<double> arr) {
    auto r = arr.unchecked<1>();
    int n = r.size();
    std::vector<double> buf(n);
    for (int i = 0; i < n; i++) buf[i] = r(i);
    return buf;
}

// vector<T> → double numpy
template<typename T>
inline void write_back(py::array_t<double> dst, const std::vector<T>& d, int n_elements) {
    std::vector<double> buf(n_elements);
    dsp_convert<T, double>(buf.data(), d.data(), n_elements);
    auto w = dst.mutable_unchecked<1>();
    for (int i = 0; i < n_elements; i++) w(i) = buf[i];
}

template<typename T>
inline void write_back(py::array_t<double> dst, const std::vector<T>& d) {
    write_back(dst, d, static_cast<int>(d.size()));
}

template<>
inline void write_back<double>(py::array_t<double> dst, const std::vector<double>& d) {
    auto w = dst.mutable_unchecked<1>();
    for (size_t i = 0; i < d.size(); i++) w(i) = d[i];
}
