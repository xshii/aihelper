#include "pa_intrinsics.h"

void f(pa_tensor_t* in, pa_tensor_t* w, pa_tensor_t* out) {
    PA_INSTR_CONV(mk_id(3, 1), in, w, out, shape(1, 2), s2, s3);
}
