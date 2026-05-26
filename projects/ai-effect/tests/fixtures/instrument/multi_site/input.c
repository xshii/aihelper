#include "pa_intrinsics.h"

void a(pa_tensor_t* x, pa_tensor_t* y, pa_tensor_t* z) {
    PA_INSTR_CONV(c0, x, y, z, s1, s2, s3);
}

void b(pa_tensor_t* x, pa_tensor_t* y, pa_tensor_t* z) {
    PA_INSTR_CONV(c1, x, y, z, s1, s2, s3);
}
