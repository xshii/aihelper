#include "intrinsics.h"
extern void *in, *out;
extern int flag;
void warmup(void) {
    commopheader h = { .opid = 7 };
    pa_conv(&h, in, out, 1);
}
void layer3(void) {
    commopheader h = { .opid = 42 };
    if (flag) {
        pa_conv(&h, in, out, 8);
    }
}
