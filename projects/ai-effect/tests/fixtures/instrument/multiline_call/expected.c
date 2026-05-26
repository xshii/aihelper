#include "pa_intrinsics.h"

void f(pa_tensor_t* in, pa_tensor_t* w, pa_tensor_t* out) {
    pa_hook_before("CONV", "CONV@input.c:4", in, w);
    PA_INSTR_CONV(c0, in, w,
                  out, s1, s2, s3);
    pa_hook_after("CONV", "CONV@input.c:4", out);
}
