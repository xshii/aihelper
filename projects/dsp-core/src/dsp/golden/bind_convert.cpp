// 绑定：类型转换
#include "bind_helpers.h"
#include "dsp/dsp_convert.h"

template<typename Src, typename Dst>
void bind_convert(py::module& m, const char* name) {
    auto fn = dsp_convert<Src, Dst>;
    m.def(name, [fn](py::array_t<float> src, py::array_t<float> dst, int count) {
        auto s = to_typed<Src>(src);
        std::vector<Dst> d(count);
        fn(d.data(), s.data(), count);
        write_back(dst, d);
    });
}

void bind_convert(py::module& m) {
    // ACC → float32
    bind_convert<q12_22_t, float>(m, "dsp_convert_q12_22_float32");
    bind_convert<q24_40_t, float>(m, "dsp_convert_q24_40_float32");

    // float32 → DUT
    bind_convert<float, int8_t> (m, "dsp_convert_float32_int8");
    bind_convert<float, int16_t>(m, "dsp_convert_float32_int16");
    bind_convert<float, int32_t>(m, "dsp_convert_float32_int32");

    // DUT → float32
    bind_convert<int8_t,  float>(m, "dsp_convert_int8_float32");
    bind_convert<int16_t, float>(m, "dsp_convert_int16_float32");
    bind_convert<int32_t, float>(m, "dsp_convert_int32_float32");

    // DUT → DUT
    bind_convert<int8_t,  int16_t>(m, "dsp_convert_int8_int16");
    bind_convert<int16_t, int8_t> (m, "dsp_convert_int16_int8");
    bind_convert<int16_t, int32_t>(m, "dsp_convert_int16_int32");
    bind_convert<int32_t, int16_t>(m, "dsp_convert_int32_int16");
}
