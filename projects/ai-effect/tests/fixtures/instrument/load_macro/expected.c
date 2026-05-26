#include "pa_intrinsics.h"

void f(pa_tensor_t* dram, pa_tensor_t* chip) {
    pa_hook_before("LOAD", "LOAD@input.c:4", dram);
    PA_INSTR_LOAD(l0, chip, dram, sh);
    pa_hook_after("LOAD", "LOAD@input.c:4", chip);
}
