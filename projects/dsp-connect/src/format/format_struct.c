/* PURPOSE: Format struct/union values — field-by-field with indentation
 * PATTERN: Iterate fields, recursively format each via DscFormatValue
 * FOR: 弱 AI 参考如何递归格式化嵌套结构体
 *
 * Output format example:
 *   {
 *     .field1 = 42,          // +0x00 UINT32
 *     .field2 = "hello",     // +0x04 char[8]
 *     .nested = {            // +0x0C config_t
 *       .x = 1,
 *       .y = 2,
 *     },
 *   }
 */

#include <string.h>

#include "format_struct.h"
#include "../core/dsc_errors.h"

/* ------------------------------------------------------------------ */
/* Helpers: emit offset + type annotation comment                      */
/* ------------------------------------------------------------------ */
static void emit_field_annotation(DscStrbuf *out,
                                  const dsc_struct_field_t *field,
                                  const DscFormatOpts *opts)
{
    if (!opts->show_offsets && !opts->show_type_names) {
        return;
    }

    DscStrbufAppend(out, " /* ");

    if (opts->show_offsets) {
        DscStrbufAppendf(out, "+0x%02X", (unsigned)field->byte_offset);
    }

    if (opts->show_offsets && opts->show_type_names) {
        DscStrbufAppend(out, " ");
    }

    if (opts->show_type_names && field->type) {
        const dsc_type_t *resolved = dsc_type_resolve_typedef(field->type);
        if (resolved && resolved->name) {
            DscStrbufAppend(out, resolved->name);
        } else if (resolved) {
            DscStrbufAppend(out, dsc_type_kind_name(resolved->kind));
        }
    }

    DscStrbufAppend(out, " */");
}

/* ------------------------------------------------------------------ */
/* Public: format a struct or union                                    */
/* ------------------------------------------------------------------ */
int DscFormatStruct(const void *data, UINT32 data_len,
                      const dsc_type_t *type, const DscFormatOpts *opts,
                      int depth, DscStrbuf *out)
{
    if (!data || !type || !out) {
        return DSC_ERR_INVALID_ARG;
    }

    const dsc_struct_field_t *fields = type->u.composite.fields;
    UINT32 field_count = type->u.composite.field_count;

    /* Handle empty struct/union */
    if (field_count == 0 || !fields) {
        DscStrbufAppend(out, "{ }");
        return DSC_OK;
    }

    /* Opening brace */
    DscStrbufAppend(out, "{\n");

    int indent_w = opts->indent_width > 0 ? opts->indent_width : 2;
    int inner_depth = depth + 1;
    int rc = DSC_OK;

    for (UINT32 i = 0; i < field_count; i++) {
        const dsc_struct_field_t *field = &fields[i];

        /* Indent */
        DscStrbufIndent(out, inner_depth * indent_w / 2);

        /* Field name */
        if (field->name) {
            DscStrbufAppendf(out, ".%s = ", field->name);
        } else {
            DscStrbufAppendf(out, ".[%zu] = ", i);
        }

        /* Compute data pointer and remaining length for this field */
        const UINT8 *field_data = (const UINT8 *)data + field->byte_offset;
        UINT32 field_data_len = 0;

        if (field->byte_offset < data_len) {
            field_data_len = data_len - field->byte_offset;
        } else {
            /* Field offset is beyond our data buffer */
            DscStrbufAppend(out, "<out of bounds>");
            if (i + 1 < field_count) {
                DscStrbufAppend(out, ",");
            }
            emit_field_annotation(out, field, opts);
            DscStrbufAppend(out, "\n");
            continue;
        }

        /* Format the field value (recursive) */
        if (field->type) {
            int field_rc = DscFormatValue(field_data, field_data_len,
                                            field->type, opts,
                                            inner_depth, out);
            if (field_rc != DSC_OK && rc == DSC_OK) {
                rc = field_rc; /* Remember first error but keep going */
            }
        } else {
            DscStrbufAppend(out, "<no type info>");
        }

        /* Trailing comma */
        DscStrbufAppend(out, ",");

        /* Offset and type annotation */
        emit_field_annotation(out, field, opts);

        DscStrbufAppend(out, "\n");
    }

    /* Closing brace at parent depth */
    DscStrbufIndent(out, depth * indent_w / 2);
    DscStrbufAppend(out, "}");

    return rc;
}
