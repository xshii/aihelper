#include "intrinsics.h"
extern void *in, *out;
void helper(commopheader* h);
void layer3(void) {
    commopheader h = { .opid = 1 };
    helper(&h);
    pa_conv(&h, in, out, 8);
}
