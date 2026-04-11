// 绑定：类型转换 — 外部只有 bint + double
#include "bind_helpers.h"
#include "dsp/dsp_convert.h"

template<typename Src, typename Dst>
void bind_cvt(py::module& m, const char* name) {
    m.def(name, [](py::array_t<double> src, py::array_t<double> dst, int count) {
        auto s = to_typed<Src>(src);
        std::vector<Dst> d(count);
        dsp_convert<Src, Dst>(d.data(), s.data(), count);
        write_back(dst, d, count);
    });
}

void bind_convert(py::module& m) {
    // double → bint（subblock 级别逐元素转换）
    bind_cvt<double, bint8> (m, "dsp_convert_double_bint8");
    bind_cvt<double, bint16>(m, "dsp_convert_double_bint16");
    bind_cvt<double, bint32>(m, "dsp_convert_double_bint32");

    // bint → double（比数用）
    bind_cvt<bint8,  double>(m, "dsp_convert_bint8_double");
    bind_cvt<bint16, double>(m, "dsp_convert_bint16_double");
    bind_cvt<bint32, double>(m, "dsp_convert_bint32_double");
}
