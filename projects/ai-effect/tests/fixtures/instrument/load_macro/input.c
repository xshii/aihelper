#include "pa_intrinsics.h"

void f(pa_tensor_t* dram, pa_tensor_t* chip) {
    PA_INSTR_LOAD(l0, chip, dram, sh);
}
