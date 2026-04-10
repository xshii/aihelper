/* PURPOSE: Format struct/union values — field-by-field with indentation
 * PATTERN: Iterate fields, recursively format each via dsc_format_value
 * FOR: 弱 AI 参考如何递归格式化嵌套结构体
 *
 * Output format example:
 *   {
 *     .field1 = 42,          // +0x00 uint32_t
 *     .field2 = "hello",     // +0x04 char[8]
 *     .nested = {            // +0x0C config_t
 *       .x = 1,
 *       .y = 2,
 *     },
 *   }
 */

#include "format_struct.h"
#include "../core/dsc_errors.h"

#include <string.h>

/* ------------------------------------------------------------------ */
/* Helpers: indent by depth * indent_width spaces                      */
/* ------------------------------------------------------------------ */
static void emit_indent(dsc_strbuf_t *out, int depth, int indent_width)
{
    int spaces = depth * indent_width;
    for (int i = 0; i < spaces; i++) {
        dsc_strbuf_append(out, " ");
    }
}

/* ------------------------------------------------------------------ */
/* Helpers: emit offset + type annotation comment                      */
/* ------------------------------------------------------------------ */
static void emit_field_annotation(dsc_strbuf_t *out,
                                  const dsc_struct_field_t *field,
                                  const dsc_format_opts_t *opts)
{
    if (!opts->show_offsets && !opts->show_type_names) {
        return;
    }

    dsc_strbuf_append(out, " /* ");

    if (opts->show_offsets) {
        dsc_strbuf_appendf(out, "+0x%02X", (unsigned)field->byte_offset);
    }

    if (opts->show_offsets && opts->show_type_names) {
        dsc_strbuf_append(out, " ");
    }

    if (opts->show_type_names && field->type) {
        const dsc_type_t *resolved = dsc_type_resolve_typedef(field->type);
        if (resolved && resolved->name) {
            dsc_strbuf_append(out, resolved->name);
        } else if (resolved) {
            dsc_strbuf_append(out, dsc_type_kind_name(resolved->kind));
        }
    }

    dsc_strbuf_append(out, " */");
}

/* ------------------------------------------------------------------ */
/* Public: format a struct or union                                    */
/* ------------------------------------------------------------------ */
int dsc_format_struct(const void *data, size_t data_len,
                      const dsc_type_t *type, const dsc_format_opts_t *opts,
                      int depth, dsc_strbuf_t *out)
{
    if (!data || !type || !out) {
        return DSC_ERR_INVALID_ARG;
    }

    const dsc_struct_field_t *fields = type->u.composite.fields;
    size_t field_count = type->u.composite.field_count;

    /* Handle empty struct/union */
    if (field_count == 0 || !fields) {
        dsc_strbuf_append(out, "{ }");
        return DSC_OK;
    }

    /* Opening brace */
    dsc_strbuf_append(out, "{\n");

    int indent_w = opts->indent_width > 0 ? opts->indent_width : 2;
    int inner_depth = depth + 1;
    int rc = DSC_OK;

    for (size_t i = 0; i < field_count; i++) {
        const dsc_struct_field_t *field = &fields[i];

        /* Indent */
        emit_indent(out, inner_depth, indent_w);

        /* Field name */
        if (field->name) {
            dsc_strbuf_appendf(out, ".%s = ", field->name);
        } else {
            dsc_strbuf_appendf(out, ".[%zu] = ", i);
        }

        /* Compute data pointer and remaining length for this field */
        const uint8_t *field_data = (const uint8_t *)data + field->byte_offset;
        size_t field_data_len = 0;

        if (field->byte_offset < data_len) {
            field_data_len = data_len - field->byte_offset;
        } else {
            /* Field offset is beyond our data buffer */
            dsc_strbuf_append(out, "<out of bounds>");
            if (i + 1 < field_count) {
                dsc_strbuf_append(out, ",");
            }
            emit_field_annotation(out, field, opts);
            dsc_strbuf_append(out, "\n");
            continue;
        }

        /* Format the field value (recursive) */
        if (field->type) {
            int field_rc = dsc_format_value(field_data, field_data_len,
                                            field->type, opts,
                                            inner_depth, out);
            if (field_rc != DSC_OK && rc == DSC_OK) {
                rc = field_rc; /* Remember first error but keep going */
            }
        } else {
            dsc_strbuf_append(out, "<no type info>");
        }

        /* Trailing comma */
        dsc_strbuf_append(out, ",");

        /* Offset and type annotation */
        emit_field_annotation(out, field, opts);

        dsc_strbuf_append(out, "\n");
    }

    /* Closing brace at parent depth */
    emit_indent(out, depth, indent_w);
    dsc_strbuf_append(out, "}");

    return rc;
}
