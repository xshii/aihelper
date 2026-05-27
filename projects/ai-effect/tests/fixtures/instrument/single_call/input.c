#include "intrinsics.h"
extern void *in, *out;
void layer3(void) {
    commopheader h = { .opid = 42, .aopid = 41 };
    pa_conv(&h, in, out, 8);
}
