/* PURPOSE: Format array values — element-by-element with index labels,
 *          hex dump fallback for byte arrays, truncation support
 * PATTERN: Index-labeled display for structured arrays, hex dump for byte arrays
 * FOR: 弱 AI 参考如何格式化不同类型的数组 */

#include "format_array.h"
#include "../core/dsc_errors.h"

#include <string.h>
#include <stdint.h>
#include <ctype.h>

/* ------------------------------------------------------------------ */
/* Helpers: detect if element type is a single-byte type (char/uint8)  */
/* suitable for hex dump display                                       */
/* ------------------------------------------------------------------ */
static int is_byte_type(const dsc_type_t *elem_type)
{
    if (!elem_type) return 0;

    const dsc_type_t *resolved = dsc_type_resolve_typedef(elem_type);
    if (!resolved) return 0;

    if (resolved->kind != DSC_TYPE_BASE) return 0;
    if (resolved->byte_size != 1) return 0;

    /* char or unsigned char */
    return (resolved->u.base.encoding == DSC_ENC_CHAR ||
            resolved->u.base.encoding == DSC_ENC_UNSIGNED ||
            resolved->u.base.encoding == DSC_ENC_SIGNED);
}

/* ------------------------------------------------------------------ */
/* Helpers: hex dump for byte arrays                                   */
/* Format: "48 65 6C 6C 6F 00"  |Hello.|                              */
/* ------------------------------------------------------------------ */
static void format_hex_dump(const uint8_t *bytes, size_t count,
                            size_t max_elems, dsc_strbuf_t *out)
{
    size_t show = count;
    if (max_elems > 0 && show > max_elems) {
        show = max_elems;
    }

    /* Hex bytes */
    dsc_strbuf_append(out, "\"");
    for (size_t i = 0; i < show; i++) {
        if (i > 0) dsc_strbuf_append(out, " ");
        dsc_strbuf_appendf(out, "%02X", bytes[i]);
    }
    dsc_strbuf_append(out, "\"");

    /* ASCII sidebar */
    dsc_strbuf_append(out, "  |");
    for (size_t i = 0; i < show; i++) {
        char c = (char)bytes[i];
        if (c >= 0x20 && c < 0x7F) {
            dsc_strbuf_appendf(out, "%c", c);
        } else {
            dsc_strbuf_append(out, ".");
        }
    }
    dsc_strbuf_append(out, "|");

    /* Truncation indicator */
    if (show < count) {
        dsc_strbuf_appendf(out, " ... (%zu more)", count - show);
    }
}

/* ------------------------------------------------------------------ */
/* Helpers: emit indent                                                */
/* ------------------------------------------------------------------ */
static void emit_indent(dsc_strbuf_t *out, int depth, int indent_width)
{
    int spaces = depth * indent_width;
    for (int i = 0; i < spaces; i++) {
        dsc_strbuf_append(out, " ");
    }
}

/* ------------------------------------------------------------------ */
/* Helpers: compute total element count from dimensions                 */
/* Multidimensional arrays: total = dim[0].count * dim[1].count * ...  */
/* ------------------------------------------------------------------ */
static size_t compute_total_elements(const dsc_array_dim_t *dims,
                                     size_t dim_count)
{
    if (!dims || dim_count == 0) return 0;

    size_t total = 1;
    for (size_t i = 0; i < dim_count; i++) {
        if (dims[i].count == 0) return 0; /* flexible array */
        total *= dims[i].count;
    }
    return total;
}

/* ------------------------------------------------------------------ */
/* Public: format an array value                                       */
/* ------------------------------------------------------------------ */
int dsc_format_array(const void *data, size_t data_len,
                     const dsc_type_t *type, const dsc_format_opts_t *opts,
                     int depth, dsc_strbuf_t *out)
{
    if (!data || !type || !out) {
        return DSC_ERR_INVALID_ARG;
    }

    const dsc_type_t *elem_type = type->u.array.element_type;
    if (!elem_type) {
        dsc_strbuf_append(out, "<array with no element type>");
        return DSC_ERR_TYPE_INCOMPLETE;
    }

    /* Compute element count and size */
    size_t total_elems = compute_total_elements(type->u.array.dims,
                                                type->u.array.dim_count);
    if (total_elems == 0) {
        dsc_strbuf_append(out, "[]");
        return DSC_OK;
    }

    size_t elem_size = dsc_type_size(elem_type);
    if (elem_size == 0) {
        dsc_strbuf_append(out, "<array of zero-size elements>");
        return DSC_ERR_TYPE_INCOMPLETE;
    }

    /* Clamp to available data */
    size_t avail_elems = data_len / elem_size;
    if (avail_elems < total_elems) {
        total_elems = avail_elems;
    }

    /* --- Special case: byte arrays get hex dump --- */
    if (is_byte_type(elem_type)) {
        format_hex_dump((const uint8_t *)data, total_elems,
                        (size_t)opts->array_max_elems, out);
        return DSC_OK;
    }

    /* --- General case: element-by-element display --- */
    size_t show_elems = total_elems;
    if (opts->array_max_elems > 0 && show_elems > (size_t)opts->array_max_elems) {
        show_elems = (size_t)opts->array_max_elems;
    }

    int indent_w = opts->indent_width > 0 ? opts->indent_width : 2;
    int inner_depth = depth + 1;
    int rc = DSC_OK;

    /* Compact display for small arrays of primitives */
    int compact = (total_elems <= 8 && elem_type->kind == DSC_TYPE_BASE);

    if (compact) {
        /* Single-line: [0] = 1, [1] = 2, [2] = 3 */
        dsc_strbuf_append(out, "{ ");

        for (size_t i = 0; i < show_elems; i++) {
            if (i > 0) dsc_strbuf_append(out, ", ");

            const uint8_t *elem_data = (const uint8_t *)data + (i * elem_size);
            size_t elem_data_len = data_len - (i * elem_size);

            dsc_strbuf_appendf(out, "[%zu] = ", i);

            int elem_rc = dsc_format_value(elem_data, elem_data_len,
                                           elem_type, opts,
                                           inner_depth, out);
            if (elem_rc != DSC_OK && rc == DSC_OK) {
                rc = elem_rc;
            }
        }

        if (show_elems < total_elems) {
            dsc_strbuf_appendf(out, ", ... (%zu more)", total_elems - show_elems);
        }

        dsc_strbuf_append(out, " }");
    } else {
        /* Multi-line display */
        dsc_strbuf_append(out, "{\n");

        for (size_t i = 0; i < show_elems; i++) {
            const uint8_t *elem_data = (const uint8_t *)data + (i * elem_size);
            size_t elem_data_len = data_len - (i * elem_size);

            emit_indent(out, inner_depth, indent_w);
            dsc_strbuf_appendf(out, "[%zu] = ", i);

            int elem_rc = dsc_format_value(elem_data, elem_data_len,
                                           elem_type, opts,
                                           inner_depth, out);
            if (elem_rc != DSC_OK && rc == DSC_OK) {
                rc = elem_rc;
            }

            dsc_strbuf_append(out, ",\n");
        }

        if (show_elems < total_elems) {
            emit_indent(out, inner_depth, indent_w);
            dsc_strbuf_appendf(out, "... (%zu more)\n", total_elems - show_elems);
        }

        emit_indent(out, depth, indent_w);
        dsc_strbuf_append(out, "}");
    }

    return rc;
}
