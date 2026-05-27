#include "intrinsics.h"
extern void *in, *out, *buf;
void layer3(void) {
    commopheader h = { .opid = 1 };
    pa_load(&h, buf, 128);
    pa_conv(&h, in, out, 8);
}
