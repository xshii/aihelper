#include "pa_intrinsics.h"

void f(pa_tensor_t* in, pa_tensor_t* w, pa_tensor_t* out) {
    PA_INSTR_CONV(c0, in, w, out, s1, s2, s3);
}
