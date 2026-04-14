// 绑定：类型转换
#include "bind_helpers.h"
#include "bind_registry.h"
#include "dsp_convert.h"

#define BIND_CONVERT(DUT, dut_name)                                                  \
    m.def("dsp_convert_double_" #dut_name,                                           \
        [](py::array_t<double> src, py::array_t<double> dst, size_t count) {         \
            auto input = to_dut<double>(src);                                        \
            std::vector<DUT> out(num_blocks<DUT>(count));                             \
            dsp_convert<DUT, double>(out.data(), input.data(), count);                \
            from_dut(dst, out, count);                                               \
        });                                                                          \
    m.def("dsp_convert_" #dut_name "_double",                                        \
        [](py::array_t<double> src, py::array_t<double> dst, size_t count) {         \
            auto input = to_dut<DUT>(src);                                           \
            std::vector<double> out(count);                                          \
            dsp_convert<double, DUT>(out.data(), input.data(), count);                \
            from_dut(dst, out);                                                      \
        });

void bind_convert(py::module& m) {
    BIND_CONVERT(BF8,  bf8)
    BIND_CONVERT(BF16, bf16)
}

#undef BIND_CONVERT

REGISTER_BIND(bind_convert)
