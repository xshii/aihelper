extern int pa_dump_enabled;
#include "intrinsics.h"
extern void *in, *out;
void helper(commopheader* h);
void layer3(void) {
    commopheader h = { .opid = 1 };
    helper(&h);
    if (pa_dump_enabled) printf("{\"kind\":\"call\",\"op\":\"pa_conv\",\"fn\":\"layer3\",\"h\":{\"opid\":%u,\"aopid\":%u},\"in\":\"%p\",\"out\":\"%p\",\"n\":%d}\n", (&h)->opid, (&h)->aopid, (void*)(in), (void*)(out), 8);
    pa_conv(&h, in, out, 8);
}
