/* PURPOSE: Format enum values — map raw integers to enumerator names,
 *          with flags-style (OR'd bitmask) detection
 * PATTERN: Exact match first, then power-of-two bitmask decomposition for flags
 * FOR: 弱 AI 参考如何做枚举值的符号化显示 */

#include "format_enum.h"
#include "../core/dsc_errors.h"
#include "../util/byteread.h"

#include <string.h>
#include <stdint.h>

/* ------------------------------------------------------------------ */
/* Helpers: try exact match against enumerator list                    */
/* Returns the name if found, NULL otherwise.                          */
/* ------------------------------------------------------------------ */
static const char *find_exact_match(const dsc_enum_value_t *values,
                                    size_t count, int64_t raw)
{
    for (size_t i = 0; i < count; i++) {
        if (values[i].value == raw) {
            return values[i].name;
        }
    }
    return NULL;
}

/* ------------------------------------------------------------------ */
/* Helpers: detect if this enum looks like a bitmask (flags-style)     */
/* Heuristic: all non-zero enumerator values are powers of two.        */
/* ------------------------------------------------------------------ */
static int is_flags_enum(const dsc_enum_value_t *values, size_t count)
{
    int has_nonzero = 0;

    for (size_t i = 0; i < count; i++) {
        int64_t v = values[i].value;

        /* Skip zero (often "NONE" flag) */
        if (v == 0) continue;

        has_nonzero = 1;

        /* Negative values cannot be power-of-two flags */
        if (v < 0) return 0;

        /* Check if power of two: v & (v-1) == 0 */
        uint64_t uv = (uint64_t)v;
        if ((uv & (uv - 1)) != 0) return 0;
    }

    return has_nonzero;
}

/* ------------------------------------------------------------------ */
/* Helpers: format flags-style enum (OR'd bitmask)                     */
/* Decomposes the value into contributing flags.                        */
/* ------------------------------------------------------------------ */
static void format_flags(const dsc_enum_value_t *values, size_t count,
                         int64_t raw, dsc_strbuf_t *out)
{
    uint64_t remaining = (uint64_t)raw;
    int first = 1;

    /* Emit each matching flag */
    for (size_t i = 0; i < count; i++) {
        uint64_t flag = (uint64_t)values[i].value;

        /* Skip zero-value enumerator unless raw is exactly zero */
        if (flag == 0) continue;

        if ((remaining & flag) == flag) {
            if (!first) {
                dsc_strbuf_append(out, " | ");
            }
            dsc_strbuf_append(out, values[i].name);
            remaining &= ~flag;
            first = 0;
        }
    }

    /* Handle the zero case */
    if (raw == 0) {
        /* Look for a zero-valued enumerator (e.g., "NONE") */
        const char *zero_name = find_exact_match(values, count, 0);
        if (zero_name) {
            dsc_strbuf_append(out, zero_name);
        } else {
            dsc_strbuf_append(out, "0");
        }
        return;
    }

    /* If there are leftover bits not covered by any flag */
    if (remaining != 0) {
        if (!first) {
            dsc_strbuf_append(out, " | ");
        }
        dsc_strbuf_appendf(out, "0x%llX", (unsigned long long)remaining);
    }

    /* Append numeric value in parens */
    dsc_strbuf_appendf(out, " (0x%02llX)", (unsigned long long)(uint64_t)raw);
}

/* ------------------------------------------------------------------ */
/* Public: format an enum value                                        */
/* ------------------------------------------------------------------ */
int dsc_format_enum(const void *data, size_t data_len,
                    const dsc_type_t *type, const dsc_format_opts_t *opts,
                    dsc_strbuf_t *out)
{
    (void)opts; /* opts reserved for future use (e.g., always-hex mode) */

    if (!data || !type || !out) {
        return DSC_ERR_INVALID_ARG;
    }

    /* Determine byte size: prefer type->byte_size, fall back to underlying */
    size_t byte_size = type->byte_size;
    if (byte_size == 0 && type->u.enumeration.underlying) {
        byte_size = type->u.enumeration.underlying->byte_size;
    }
    if (byte_size == 0 || data_len < byte_size) {
        dsc_strbuf_append(out, "<incomplete enum>");
        return DSC_ERR_TYPE_INCOMPLETE;
    }

    int64_t raw = dsc_read_signed(data, byte_size);

    const dsc_enum_value_t *values = type->u.enumeration.values;
    size_t value_count = type->u.enumeration.value_count;

    /* No enumerators defined — just show the number */
    if (!values || value_count == 0) {
        dsc_strbuf_appendf(out, "%lld", (long long)raw);
        return DSC_OK;
    }

    /* Try exact match first */
    const char *name = find_exact_match(values, value_count, raw);
    if (name) {
        dsc_strbuf_append(out, name);
        dsc_strbuf_appendf(out, " (%lld)", (long long)raw);
        return DSC_OK;
    }

    /* No exact match — try flags-style decomposition if it looks like a bitmask */
    if (is_flags_enum(values, value_count)) {
        format_flags(values, value_count, raw, out);
        return DSC_OK;
    }

    /* Fallback: show numeric value only */
    dsc_strbuf_appendf(out, "%lld /* unknown enumerator */", (long long)raw);

    return DSC_OK;
}
