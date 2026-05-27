#include "intrinsics.h"
extern void *in, *out;
void layer3(void) {
    commopheader h = { .opid = 1 };
    _emit(&h);
    pa_conv(&h, in, out, 8);
}
