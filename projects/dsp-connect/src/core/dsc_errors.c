/* PURPOSE: 错误码 → 字符串，由 X-macro 自动生成 */

#include <stddef.h>

#include "dsc_errors.h"

/* Expand X-macro to string table */
#define X_ENTRY(name, code, desc) { code, desc },
static const struct { int code; const char *msg; } error_table[] = {
    DSC_ERROR_TABLE(X_ENTRY)
};
#undef X_ENTRY

#define ARRAY_LEN(a) (sizeof(a) / sizeof((a)[0]))

const char *DscStrerror(int err)
{
    for (UINT32 i = 0; i < ARRAY_LEN(error_table); i++) {
        if (error_table[i].code == err) {
            return error_table[i].msg;
        }
    }
    return "unknown error";
}
