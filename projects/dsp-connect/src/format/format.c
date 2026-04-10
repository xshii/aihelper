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
dsc_format_opts_t dsc_format_opts_default(void)
{
    dsc_format_opts_t opts;
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
/* Every sub-formatter that recurses calls this, not dsc_format().     */
/* ------------------------------------------------------------------ */
int dsc_format_value(const void *data, size_t data_len,
                     const dsc_type_t *type, const dsc_format_opts_t *opts,
                     int depth, dsc_strbuf_t *out)
{
    /* --- Guard: NULL inputs --- */
    if (!data || !type || !out) {
        return DSC_ERR_INVALID_ARG;
    }

    /* --- Resolve typedef / const / volatile chain --- */
    const dsc_type_t *resolved = dsc_type_resolve_typedef(type);
    if (!resolved) {
        dsc_strbuf_append(out, "<unresolved type>");
        return DSC_ERR_TYPE_INCOMPLETE;
    }

    /* --- Optional: prefix with type name --- */
    if (opts->show_type_names && resolved->name) {
        dsc_strbuf_appendf(out, "(%s) ", resolved->name);
    }

    /* --- Dispatch by kind --- */
    switch (resolved->kind) {

    case DSC_TYPE_BASE:
        return dsc_format_primitive(data, data_len, resolved, opts, out);

    case DSC_TYPE_STRUCT:
    case DSC_TYPE_UNION:
        /* Check max_depth limit */
        if (opts->max_depth > 0 && depth >= opts->max_depth) {
            dsc_strbuf_append(out, "{ ... }");
            return DSC_OK;
        }
        return dsc_format_struct(data, data_len, resolved, opts, depth, out);

    case DSC_TYPE_ENUM:
        return dsc_format_enum(data, data_len, resolved, opts, out);

    case DSC_TYPE_ARRAY:
        return dsc_format_array(data, data_len, resolved, opts, depth, out);

    case DSC_TYPE_POINTER:
        return dsc_format_pointer(data, data_len, resolved, opts, out);

    case DSC_TYPE_BITFIELD:
        return dsc_format_bitfield(data, data_len, resolved, opts, out);

    case DSC_TYPE_VOID:
        dsc_strbuf_append(out, "void");
        return DSC_OK;

    case DSC_TYPE_FUNC:
        dsc_strbuf_append(out, "<function>");
        return DSC_OK;

    /* typedef/const/volatile should have been resolved above */
    case DSC_TYPE_TYPEDEF:
    case DSC_TYPE_CONST:
    case DSC_TYPE_VOLATILE:
        dsc_strbuf_append(out, "<unresolved modifier>");
        return DSC_ERR_TYPE_UNKNOWN;

    default:
        dsc_strbuf_appendf(out, "<unknown type kind %d>", (int)resolved->kind);
        return DSC_ERR_TYPE_UNKNOWN;
    }
}

/* ------------------------------------------------------------------ */
/* Public: main entry point                                            */
/* ------------------------------------------------------------------ */
int dsc_format(const void *data, size_t data_len,
               const dsc_type_t *type, const dsc_format_opts_t *opts,
               dsc_strbuf_t *out)
{
    /* Use defaults if caller passed NULL */
    dsc_format_opts_t default_opts;
    if (!opts) {
        default_opts = dsc_format_opts_default();
        opts = &default_opts;
    }

    return dsc_format_value(data, data_len, type, opts, 0, out);
}

/* ------------------------------------------------------------------ */
/* Public: convenience — format to newly allocated string              */
/* ------------------------------------------------------------------ */
char *dsc_format_str(const void *data, size_t data_len,
                     const dsc_type_t *type, const dsc_format_opts_t *opts)
{
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 256);

    int rc = dsc_format(data, data_len, type, opts, &sb);
    if (rc != DSC_OK) {
        /* On error, still return what we have (may contain partial + error text) */
        /* Caller can check return by calling dsc_format() directly if they care */
    }

    /* Transfer ownership: duplicate the string, free the buffer internals */
    const char *cstr = dsc_strbuf_cstr(&sb);
    char *result = NULL;
    if (cstr) {
        size_t len = sb.len;
        result = malloc(len + 1);
        if (result) {
            memcpy(result, cstr, len + 1);
        }
    }

    dsc_strbuf_free(&sb);
    return result;
}
