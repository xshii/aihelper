#include "pa_intrinsics.h"

void layer3(pa_tensor_t* in, pa_tensor_t* w, pa_tensor_t* out) {
    PA_INSTR_CONV(conv_l3, in, w, out, ish, wsh, osh);
}
