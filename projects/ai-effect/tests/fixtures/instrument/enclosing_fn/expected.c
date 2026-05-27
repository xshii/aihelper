extern int pa_dump_enabled;
#include "intrinsics.h"
extern void *in, *out;
extern int flag;
void warmup(void) {
    commopheader h = { .opid = 7 };
    if (pa_dump_enabled) printf("{\"kind\":\"call\",\"op\":\"pa_conv\",\"fn\":\"warmup\",\"h\":{\"opid\":%u,\"aopid\":%u},\"in\":\"%p\",\"out\":\"%p\",\"n\":%d}\n", (&h)->opid, (&h)->aopid, (void*)(in), (void*)(out), 1);
    pa_conv(&h, in, out, 1);
}
void layer3(void) {
    commopheader h = { .opid = 42 };
    if (flag) {
        if (pa_dump_enabled) printf("{\"kind\":\"call\",\"op\":\"pa_conv\",\"fn\":\"layer3\",\"h\":{\"opid\":%u,\"aopid\":%u},\"in\":\"%p\",\"out\":\"%p\",\"n\":%d}\n", (&h)->opid, (&h)->aopid, (void*)(in), (void*)(out), 8);
        pa_conv(&h, in, out, 8);
    }
}
