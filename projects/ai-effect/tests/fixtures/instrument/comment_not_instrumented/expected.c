#include "pa_intrinsics.h"

/* 块注释里出现 PA_INSTR_CONV(c0, in, w, out, s1, s2, s3); 不应被插桩 */
void f(pa_tensor_t* in) {
    // 行注释里的 PA_INSTR_CONV(c9, in, in, in, s, s, s); 也不应被插桩
    (void)in;
}
