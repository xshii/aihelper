#include "intrinsics.h"
int layer3(void) {
    commopheader h = { .opid = 42 };
    int rc = pa_query(&h);
    return rc;
}
