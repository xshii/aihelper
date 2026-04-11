// 绑定：向量运算
#include "bind_helpers.h"
#include "dsp/dsp_vector.h"

template<typename T>
void bind_add(py::module& m, const char* name) {
    auto fn = dsp_add<T>;
    m.def(name, [fn](py::array_t<float> dst, py::array_t<float> src0, py::array_t<float> src1, int count) {
        auto s0 = to_typed<T>(src0); auto s1 = to_typed<T>(src1);
        std::vector<T> d(count);
        fn(d.data(), s0.data(), s1.data(), count);
        write_back(dst, d);
    });
}

template<typename T>
void bind_abs(py::module& m, const char* name) {
    auto fn = dsp_abs<T>;
    m.def(name, [fn](py::array_t<float> dst, py::array_t<float> src0, int count) {
        auto s0 = to_typed<T>(src0);
        std::vector<T> d(count);
        fn(d.data(), s0.data(), count);
        write_back(dst, d);
    });
}

template<typename Src0, typename Src1, typename Dst0, typename Acc>
void bind_binary(py::module& m, const char* name) {
    auto fn = dsp_mul<Src0, Src1, Dst0, Acc>;  // mul/xcorr 签名相同
    m.def(name, [fn](py::array_t<float> dst, py::array_t<float> src0, py::array_t<float> src1, int count) {
        auto s0 = to_typed<Src0>(src0); auto s1 = to_typed<Src1>(src1);
        std::vector<Dst0> d(count);
        fn(d.data(), s0.data(), s1.data(), count);
        write_back(dst, d);
    });
}

template<typename Src0, typename Src1, typename Dst0, typename Acc>
void bind_xcorr(py::module& m, const char* name) {
    auto fn = dsp_xcorr<Src0, Src1, Dst0, Acc>;
    m.def(name, [fn](py::array_t<float> dst, py::array_t<float> src0, py::array_t<float> src1, int count) {
        auto s0 = to_typed<Src0>(src0); auto s1 = to_typed<Src1>(src1);
        std::vector<Dst0> d(count);
        fn(d.data(), s0.data(), s1.data(), count);
        write_back(dst, d);
    });
}

void bind_vector(py::module& m) {
    // dsp_add<T> — 函数名: dsp_add_type
    bind_add<int16_t>(m, "dsp_add_int16");
    bind_add<int32_t>(m, "dsp_add_int32");

    // dsp_mul<Src0, Src1, Dst0, Acc>
    bind_binary<int16_t, int16_t, q12_22_t, Q12_22>(m, "dsp_mul_int16_int16_q12_22_q12_22");

    // dsp_abs<T>
    bind_abs<int16_t>(m, "dsp_abs_int16");
    bind_abs<int32_t>(m, "dsp_abs_int32");

    // dsp_xcorr<Src0, Src1, Dst0, Acc>
    bind_xcorr<int16_t, int16_t, q12_22_t, Q12_22>(m, "dsp_xcorr_int16_int16_q12_22_q12_22");
    bind_xcorr<int32_t, int32_t, q24_40_t, Q24_40>(m, "dsp_xcorr_int32_int32_q24_40_q24_40");
}
