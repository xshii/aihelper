extern int pa_dump_enabled;
#include "intrinsics.h"
extern void *in, *out, *buf;
void layer3(void) {
    commopheader h = { .opid = 1 };
    if (pa_dump_enabled) printf("{\"kind\":\"call\",\"op\":\"pa_load\",\"fn\":\"layer3\",\"h\":{\"opid\":%u,\"aopid\":%u},\"dst\":\"%p\",\"n\":%d}\n", (&h)->opid, (&h)->aopid, (void*)(buf), 128);
    pa_load(&h, buf, 128);
    if (pa_dump_enabled) printf("{\"kind\":\"call\",\"op\":\"pa_conv\",\"fn\":\"layer3\",\"h\":{\"opid\":%u,\"aopid\":%u},\"in\":\"%p\",\"out\":\"%p\",\"n\":%d}\n", (&h)->opid, (&h)->aopid, (void*)(in), (void*)(out), 8);
    pa_conv(&h, in, out, 8);
}
