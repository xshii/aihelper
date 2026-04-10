/* PURPOSE: Dispatcher — resolves typedefs, then switches on type->kind to
 *          call the right sub-formatter (struct, enum, array, primitive)
 * PATTERN: Dispatcher — resolve typedefs, switch on type->kind, delegate to sub-formatters
 * FOR: 弱 AI 参考如何做类型分派和递归格式化 */

#include <stdlib.h>
#include <string.h>

#include "format.h"
#include "format_array.h"
#include "format_enum.h"
#include "format_primitive.h"
#include "format_struct.h"
#include "../core/dsc_errors.h"

/* ------------------------------------------------------------------ */
/* Default options — Layer 0 (zero config)                             */
/* ------------------------------------------------------------------ */
DscFormatOpts DscFormatOptsDefault(void)
{
    DscFormatOpts opts;
    memset(&opts, 0, sizeof(opts));

    opts.max_depth       = 0;   /* unlimited */
    opts.array_max_elems = 0;   /* show all  */
    opts.hex_integers    = 0;   /* decimal   */
    opts.show_offsets    = 0;   /* no        */
    opts.show_type_names = 0;   /* no        */
    opts.indent_width    = 2;   /* 2 spaces  */

    return opts;
}

/* ------------------------------------------------------------------ */
/* Internal: format with depth tracking                                */
/* Every sub-formatter that recurses calls this, not DscFormat().     */
/* ------------------------------------------------------------------ */
int DscFormatValue(const void *data, UINT32 data_len,
                     const dsc_type_t *type, const DscFormatOpts *opts,
                     int depth, DscStrbuf *out)
{
    /* --- Guard: NULL inputs --- */
    if (!data || !type || !out) {
        return DSC_ERR_INVALID_ARG;
    }

    /* --- Resolve typedef / const / volatile chain --- */
    const dsc_type_t *resolved = dsc_type_resolve_typedef(type);
    if (!resolved) {
        DscStrbufAppend(out, "<unresolved type>");
        return DSC_ERR_TYPE_INCOMPLETE;
    }

    /* --- Optional: prefix with type name --- */
    if (opts->show_type_names && resolved->name) {
        DscStrbufAppendf(out, "(%s) ", resolved->name);
    }

    /* --- Dispatch by kind --- */
    switch (resolved->kind) {

    case DSC_TYPE_BASE:
        return DscFormatPrimitive(data, data_len, resolved, opts, out);

    case DSC_TYPE_STRUCT:
    case DSC_TYPE_UNION:
        /* Check max_depth limit */
        if (opts->max_depth > 0 && depth >= opts->max_depth) {
            DscStrbufAppend(out, "{ ... }");
            return DSC_OK;
        }
        return DscFormatStruct(data, data_len, resolved, opts, depth, out);

    case DSC_TYPE_ENUM:
        return DscFormatEnum(data, data_len, resolved, opts, out);

    case DSC_TYPE_ARRAY:
        return DscFormatArray(data, data_len, resolved, opts, depth, out);

    case DSC_TYPE_POINTER:
        return DscFormatPointer(data, data_len, resolved, opts, out);

    case DSC_TYPE_BITFIELD:
        return DscFormatBitfield(data, data_len, resolved, opts, out);

    case DSC_TYPE_VOID:
        DscStrbufAppend(out, "void");
        return DSC_OK;

    case DSC_TYPE_FUNC:
        DscStrbufAppend(out, "<function>");
        return DSC_OK;

    /* typedef/const/volatile should have been resolved above */
    case DSC_TYPE_TYPEDEF:
    case DSC_TYPE_CONST:
    case DSC_TYPE_VOLATILE:
        DscStrbufAppend(out, "<unresolved modifier>");
        return DSC_ERR_TYPE_UNKNOWN;

    default:
        DscStrbufAppendf(out, "<unknown type kind %d>", (int)resolved->kind);
        return DSC_ERR_TYPE_UNKNOWN;
    }
}

/* ------------------------------------------------------------------ */
/* Public: main entry point                                            */
/* ------------------------------------------------------------------ */
int DscFormat(const void *data, UINT32 data_len,
               const dsc_type_t *type, const DscFormatOpts *opts,
               DscStrbuf *out)
{
    /* Use defaults if caller passed NULL */
    DscFormatOpts default_opts;
    if (!opts) {
        default_opts = DscFormatOptsDefault();
        opts = &default_opts;
    }

    return DscFormatValue(data, data_len, type, opts, 0, out);
}

/* ------------------------------------------------------------------ */
/* Public: convenience — format to newly allocated string              */
/* ------------------------------------------------------------------ */
char *DscFormatStr(const void *data, UINT32 data_len,
                     const dsc_type_t *type, const DscFormatOpts *opts)
{
    DscStrbuf sb;
    DscStrbufInit(&sb, 256);

    int rc = DscFormat(data, data_len, type, opts, &sb);
    if (rc != DSC_OK) {
        /* On error, still return what we have (may contain partial + error text) */
        /* Caller can check return by calling DscFormat() directly if they care */
    }

    /* Transfer ownership: duplicate the string, free the buffer internals */
    const char *cstr = DscStrbufCstr(&sb);
    char *result = NULL;
    if (cstr) {
        UINT32 len = sb.len;
        result = malloc(len + 1);
        if (result) {
            memcpy(result, cstr, len + 1);
        }
    }

    DscStrbufFree(&sb);
    return result;
}
