// 绑定：向量运算
#include "bind_helpers.h"
#include "dsp/dsp_vector.h"

template<typename T>
void bind_add(py::module& m, const char* name) {
    m.def(name, [](py::array_t<double> dst, py::array_t<double> src0, py::array_t<double> src1, int count) {
        auto s0 = to_typed<T>(src0); auto s1 = to_typed<T>(src1);
        std::vector<T> d(num_blocks<T>(count));
        dsp_add<T>(d.data(), s0.data(), s1.data(), count);
        write_back(dst, d, count);
    });
}

template<typename T>
void bind_abs(py::module& m, const char* name) {
    m.def(name, [](py::array_t<double> dst, py::array_t<double> src0, int count) {
        auto s0 = to_typed<T>(src0);
        std::vector<T> d(num_blocks<T>(count));
        dsp_abs<T>(d.data(), s0.data(), count);
        write_back(dst, d, count);
    });
}

template<typename Src0, typename Src1, typename Dst0,
         void(*Fn)(Dst0*, const Src0*, const Src1*, int)>
void bind_binary(py::module& m, const char* name) {
    m.def(name, [](py::array_t<double> dst, py::array_t<double> src0, py::array_t<double> src1, int count) {
        auto s0 = to_typed<Src0>(src0); auto s1 = to_typed<Src1>(src1);
        std::vector<Dst0> d(num_blocks<Dst0>(count));
        Fn(d.data(), s0.data(), s1.data(), count);
        write_back(dst, d, count);
    });
}

void bind_vector(py::module& m) {
    bind_add<bint16>(m, "dsp_add_bint16");
    bind_add<bint32>(m, "dsp_add_bint32");

    bind_binary<bint16, bint16, bint32,
        dsp_mul<bint16, bint16, bint32>>(m, "dsp_mul_bint16_bint16_bint32");

    bind_abs<bint16>(m, "dsp_abs_bint16");
    bind_abs<bint32>(m, "dsp_abs_bint32");

    bind_binary<bint16, bint16, bint32,
        dsp_xcorr<bint16, bint16, bint32>>(m, "dsp_xcorr_bint16_bint16_bint32");
    bind_binary<bint32, bint32, bint32,
        dsp_xcorr<bint32, bint32, bint32>>(m, "dsp_xcorr_bint32_bint32_bint32");
}
