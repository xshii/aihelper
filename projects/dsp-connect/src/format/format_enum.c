/* PURPOSE: Format enum values — map raw integers to enumerator names,
 *          with flags-style (OR'd bitmask) detection
 * PATTERN: Exact match first, then power-of-two bitmask decomposition for flags
 * FOR: 弱 AI 参考如何做枚举值的符号化显示 */

#include <stdint.h>
#include <string.h>

#include "format_enum.h"
#include "../core/dsc_errors.h"
#include "../util/byteread.h"

/* ------------------------------------------------------------------ */
/* Helpers: try exact match against enumerator list                    */
/* Returns the name if found, NULL otherwise.                          */
/* ------------------------------------------------------------------ */
static const char *find_exact_match(const dsc_enum_value_t *values,
                                    UINT32 count, INT64 raw)
{
    for (UINT32 i = 0; i < count; i++) {
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
static int is_flags_enum(const dsc_enum_value_t *values, UINT32 count)
{
    int has_nonzero = 0;

    for (UINT32 i = 0; i < count; i++) {
        INT64 v = values[i].value;

        /* Skip zero (often "NONE" flag) */
        if (v == 0) {
            continue;
        }

        has_nonzero = 1;

        /* Negative values cannot be power-of-two flags */
        if (v < 0) {
            return 0;
        }

        /* Check if power of two: v & (v-1) == 0 */
        UINT64 uv = (UINT64)v;
        if ((uv & (uv - 1)) != 0) {
            return 0;
        }
    }

    return has_nonzero;
}

/* ------------------------------------------------------------------ */
/* Helpers: format flags-style enum (OR'd bitmask)                     */
/* Decomposes the value into contributing flags.                        */
/* ------------------------------------------------------------------ */
static void format_flags(const dsc_enum_value_t *values, UINT32 count,
                         INT64 raw, DscStrbuf *out)
{
    UINT64 remaining = (UINT64)raw;
    int first = 1;

    /* Emit each matching flag */
    for (UINT32 i = 0; i < count; i++) {
        UINT64 flag = (UINT64)values[i].value;

        /* Skip zero-value enumerator unless raw is exactly zero */
        if (flag == 0) {
            continue;
        }

        if ((remaining & flag) == flag) {
            if (!first) {
                DscStrbufAppend(out, " | ");
            }
            DscStrbufAppend(out, values[i].name);
            remaining &= ~flag;
            first = 0;
        }
    }

    /* Handle the zero case */
    if (raw == 0) {
        /* Look for a zero-valued enumerator (e.g., "NONE") */
        const char *zero_name = find_exact_match(values, count, 0);
        if (zero_name) {
            DscStrbufAppend(out, zero_name);
        } else {
            DscStrbufAppend(out, "0");
        }
        return;
    }

    /* If there are leftover bits not covered by any flag */
    if (remaining != 0) {
        if (!first) {
            DscStrbufAppend(out, " | ");
        }
        DscStrbufAppendf(out, "0x%llX", (unsigned long long)remaining);
    }

    /* Append numeric value in parens */
    DscStrbufAppendf(out, " (0x%02llX)", (unsigned long long)(UINT64)raw);
}

/* ------------------------------------------------------------------ */
/* Public: format an enum value                                        */
/* ------------------------------------------------------------------ */
int DscFormatEnum(const void *data, UINT32 data_len,
                    const dsc_type_t *type, const DscFormatOpts *opts,
                    DscStrbuf *out)
{
    (void)opts; /* opts reserved for future use (e.g., always-hex mode) */

    if (!data || !type || !out) {
        return DSC_ERR_INVALID_ARG;
    }

    /* Determine byte size: prefer type->byte_size, fall back to underlying */
    UINT32 byte_size = type->byte_size;
    if (byte_size == 0 && type->u.enumeration.underlying) {
        byte_size = type->u.enumeration.underlying->byte_size;
    }
    if (byte_size == 0 || data_len < byte_size) {
        DscStrbufAppend(out, "<incomplete enum>");
        return DSC_ERR_TYPE_INCOMPLETE;
    }

    INT64 raw = DscReadSigned(data, byte_size);

    const dsc_enum_value_t *values = type->u.enumeration.values;
    UINT32 value_count = type->u.enumeration.value_count;

    /* No enumerators defined — just show the number */
    if (!values || value_count == 0) {
        DscStrbufAppendf(out, "%lld", (long long)raw);
        return DSC_OK;
    }

    /* Try exact match first */
    const char *name = find_exact_match(values, value_count, raw);
    if (name) {
        DscStrbufAppend(out, name);
        DscStrbufAppendf(out, " (%lld)", (long long)raw);
        return DSC_OK;
    }

    /* No exact match — try flags-style decomposition if it looks like a bitmask */
    if (is_flags_enum(values, value_count)) {
        format_flags(values, value_count, raw, out);
        return DSC_OK;
    }

    /* Fallback: show numeric value only */
    DscStrbufAppendf(out, "%lld /* unknown enumerator */", (long long)raw);

    return DSC_OK;
}
