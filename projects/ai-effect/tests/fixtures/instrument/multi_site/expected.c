#include "pa_intrinsics.h"

void a(pa_tensor_t* x, pa_tensor_t* y, pa_tensor_t* z) {
    pa_hook_before("CONV", "CONV@input.c:4", x, y);
    PA_INSTR_CONV(c0, x, y, z, s1, s2, s3);
    pa_hook_after("CONV", "CONV@input.c:4", z);
}

void b(pa_tensor_t* x, pa_tensor_t* y, pa_tensor_t* z) {
    pa_hook_before("CONV", "CONV@input.c:8", x, y);
    PA_INSTR_CONV(c1, x, y, z, s1, s2, s3);
    pa_hook_after("CONV", "CONV@input.c:8", z);
}
