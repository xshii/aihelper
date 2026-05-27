extern int pa_dump_enabled;
#include "intrinsics.h"
int layer3(void) {
    commopheader h = { .opid = 42 };
    if (pa_dump_enabled) printf("{\"kind\":\"call\",\"op\":\"pa_query\",\"fn\":\"layer3\",\"h\":{\"opid\":%u,\"aopid\":%u}}\n", (&h)->opid, (&h)->aopid);
    int rc = pa_query(&h);
    return rc;
}
