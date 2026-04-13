// Python double numpy <-> C++ DUT block 的桥接
#pragma once
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <vector>
#include "dsp_convert.h"

namespace py = pybind11;

// subblock 元素数
template<typename DUT> struct subblock_size;
template<> struct subblock_size<BF8>  { static constexpr size_t value = BF8_BLOCK_SIZE; };
template<> struct subblock_size<BF16> { static constexpr size_t value = BF16_BLOCK_SIZE; };
template<> struct subblock_size<double> { static constexpr size_t value = 1; };

// 按 subblock 数向上取整
template<typename DUT>
inline size_t num_blocks(size_t n_elements) {
    constexpr size_t sz = subblock_size<DUT>::value;
    return (n_elements + sz - 1) / sz;
}

#pragma region ToDut

// double numpy → vector<DUT>
template<typename DUT>
inline std::vector<DUT> to_dut(py::array_t<double> arr) {
    auto r = arr.unchecked<1>();
    size_t n = r.size();
    std::vector<DUT> buf(num_blocks<DUT>(n));
    dsp_convert<DUT, double>(buf.data(), const_cast<double*>(r.data(0)), n);
    return buf;
}

// double 特化: 直接拷贝
template<>
inline std::vector<double> to_dut<double>(py::array_t<double> arr) {
    auto r = arr.unchecked<1>();
    size_t n = r.size();
    std::vector<double> buf(n);
    for (size_t i = 0; i < n; i++) buf[i] = r(i);
    return buf;
}

#pragma endregion

#pragma region FromDut

// vector<DUT> → double numpy
template<typename DUT>
inline void from_dut(py::array_t<double> dst, std::vector<DUT>& d, size_t n_elements) {
    std::vector<double> buf(n_elements);
    dsp_convert<double, DUT>(buf.data(), d.data(), n_elements);
    auto w = dst.mutable_unchecked<1>();
    for (size_t i = 0; i < n_elements; i++) w(i) = buf[i];
}

template<typename DUT>
inline void from_dut(py::array_t<double> dst, std::vector<DUT>& d) {
    from_dut(dst, d, d.size() * subblock_size<DUT>::value);
}

template<>
inline void from_dut<double>(py::array_t<double> dst, std::vector<double>& d) {
    auto w = dst.mutable_unchecked<1>();
    for (size_t i = 0; i < d.size(); i++) w(i) = d[i];
}

#pragma endregion
