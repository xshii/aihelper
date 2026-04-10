/* PURPOSE: Format primitive (base) types — integers, floats, bool, char,
 *          pointers, bitfields, and Q-format fixed-point values
 * PATTERN: X-macro dispatch by base encoding, Q-format fixed-point detection from type name
 * FOR: 弱 AI 参考如何格式化 DSP 中常见的基本类型（含定点数） */

#include <ctype.h>
#include <math.h>
#include <stdint.h>
#include <string.h>

#include "format_primitive.h"
#include "../core/dsc_errors.h"
#include "../util/byteread.h"

/* ------------------------------------------------------------------ */
/* Helpers: format signed integer                                      */
/* ------------------------------------------------------------------ */
static void format_signed_int(INT64 val, UINT32 byte_size,
                              int hex, DscStrbuf *out)
{
    if (hex) {
        /* Show hex with appropriate width */
        int digits = (int)(byte_size * 2);
        if (val < 0) {
            DscStrbufAppendf(out, "-0x%0*llX",
                               digits, (unsigned long long)(-val));
        } else {
            DscStrbufAppendf(out, "0x%0*llX",
                               digits, (unsigned long long)val);
        }
    } else {
        DscStrbufAppendf(out, "%lld", (long long)val);
    }
}

/* ------------------------------------------------------------------ */
/* Helpers: format unsigned integer                                    */
/* ------------------------------------------------------------------ */
static void format_unsigned_int(UINT64 val, UINT32 byte_size,
                                int hex, DscStrbuf *out)
{
    if (hex) {
        int digits = (int)(byte_size * 2);
        DscStrbufAppendf(out, "0x%0*llX",
                           digits, (unsigned long long)val);
    } else {
        DscStrbufAppendf(out, "%llu", (unsigned long long)val);
    }
}

/* ------------------------------------------------------------------ */
/* Helpers: detect Q-format fixed-point from type name                 */
/* Q-format is common in DSP: "q15", "q31", "Q1.15", "Q16.16" etc.   */
/* Returns fractional bit count, or 0 if not Q-format.                */
/* ------------------------------------------------------------------ */
static int detect_qformat(const char *name, int *out_int_bits, int *out_frac_bits)
{
    if (!name) {
        return 0;
    }

    /* Match "q<N>" or "Q<N>" — implies Q1.<N> (one sign bit, N frac bits) */
    if ((name[0] == 'q' || name[0] == 'Q') && name[1] >= '0' && name[1] <= '9') {
        const char *p = name + 1;

        /* Check for "Qm.n" format */
        int m = 0;
        int n = 0;
        while (*p >= '0' && *p <= '9') {
            m = m * 10 + (*p - '0');
            p++;
        }
        if (*p == '.') {
            /* Qm.n format */
            p++;
            while (*p >= '0' && *p <= '9') {
                n = n * 10 + (*p - '0');
                p++;
            }
            *out_int_bits = m;
            *out_frac_bits = n;
            return 1;
        }
        /* Just "qN" — shorthand for Q1.N (signed, N fractional bits) */
        *out_int_bits = 1;
        *out_frac_bits = m;
        return 1;
    }

    return 0;
}

static void format_qformat(INT64 raw, int int_bits, int frac_bits,
                            DscStrbuf *out)
{
    (void)int_bits; /* int_bits included for completeness */
    double scale = (double)(1LL << frac_bits);
    double value = (double)raw / scale;
    DscStrbufAppendf(out, "%.6f", value);
    DscStrbufAppendf(out, " (Q%d.%d raw=%lld)",
                       int_bits, frac_bits, (long long)raw);
}

/* ------------------------------------------------------------------ */
/* Helpers: format float                                               */
/* ------------------------------------------------------------------ */
static void format_float(const void *data, UINT32 byte_size, DscStrbuf *out)
{
    if (byte_size == 4) {
        float f;
        memcpy(&f, data, 4);
        if (isnan(f)) {
            DscStrbufAppend(out, "NaN");
        } else if (isinf(f)) {
            DscStrbufAppend(out, f > 0 ? "+Inf" : "-Inf");
        } else {
            DscStrbufAppendf(out, "%.7g", (double)f);
        }
    } else if (byte_size == 8) {
        double d;
        memcpy(&d, data, 8);
        if (isnan(d)) {
            DscStrbufAppend(out, "NaN");
        } else if (isinf(d)) {
            DscStrbufAppend(out, d > 0 ? "+Inf" : "-Inf");
        } else {
            DscStrbufAppendf(out, "%.15g", d);
        }
    } else {
        DscStrbufAppendf(out, "<float%zu?>", byte_size * 8);
    }
}

/* ------------------------------------------------------------------ */
/* Helpers: format bool                                                */
/* ------------------------------------------------------------------ */
static void format_bool(const void *data, UINT32 byte_size, DscStrbuf *out)
{
    UINT64 val = DscReadUnsigned(data, byte_size);
    DscStrbufAppend(out, val ? "true" : "false");
}

/* ------------------------------------------------------------------ */
/* Helpers: format char                                                */
/* ------------------------------------------------------------------ */
static void format_char(const void *data, DscStrbuf *out)
{
    UINT8 c;
    memcpy(&c, data, 1);

    if (c >= 0x20 && c < 0x7F) {
        /* Printable ASCII */
        DscStrbufAppendf(out, "'%c'", (char)c);
    } else {
        /* Non-printable: show hex escape */
        DscStrbufAppendf(out, "'\\x%02X'", c);
    }
}

/* ------------------------------------------------------------------ */
/* Public: format a base (primitive) type                              */
/* ------------------------------------------------------------------ */
int DscFormatPrimitive(const void *data, UINT32 data_len,
                         const dsc_type_t *type, const DscFormatOpts *opts,
                         DscStrbuf *out)
{
    if (!data || !type || !out) {
        return DSC_ERR_INVALID_ARG;
    }

    UINT32 byte_size = type->byte_size;
    if (byte_size == 0 || data_len < byte_size) {
        DscStrbufAppend(out, "<incomplete>");
        return DSC_ERR_TYPE_INCOMPLETE;
    }

    /* --- Check for Q-format fixed-point (common in DSP) --- */
    int q_int_bits = 0;
    int q_frac_bits = 0;
    if (type->u.base.encoding == DSC_ENC_SIGNED &&
        detect_qformat(type->name, &q_int_bits, &q_frac_bits)) {
        INT64 raw = DscReadSigned(data, byte_size);
        format_qformat(raw, q_int_bits, q_frac_bits, out);
        return DSC_OK;
    }

    /* --- X-macro style dispatch on encoding --- */
    switch (type->u.base.encoding) {

    case DSC_ENC_SIGNED: {
        INT64 val = DscReadSigned(data, byte_size);
        format_signed_int(val, byte_size, opts->hex_integers, out);
        return DSC_OK;
    }

    case DSC_ENC_UNSIGNED: {
        UINT64 val = DscReadUnsigned(data, byte_size);
        format_unsigned_int(val, byte_size, opts->hex_integers, out);
        return DSC_OK;
    }

    case DSC_ENC_FLOAT:
        format_float(data, byte_size, out);
        return DSC_OK;

    case DSC_ENC_BOOL:
        format_bool(data, byte_size, out);
        return DSC_OK;

    case DSC_ENC_CHAR:
        format_char(data, out);
        return DSC_OK;

    default:
        DscStrbufAppendf(out, "<unknown encoding %d>",
                           (int)type->u.base.encoding);
        return DSC_ERR_TYPE_UNKNOWN;
    }
}

/* ------------------------------------------------------------------ */
/* Public: format a pointer value                                      */
/* ------------------------------------------------------------------ */
int DscFormatPointer(const void *data, UINT32 data_len,
                       const dsc_type_t *type, const DscFormatOpts *opts,
                       DscStrbuf *out)
{
    (void)opts;

    if (!data || !type || !out) {
        return DSC_ERR_INVALID_ARG;
    }

    UINT32 byte_size = type->byte_size;
    if (byte_size == 0 || data_len < byte_size) {
        DscStrbufAppend(out, "<incomplete ptr>");
        return DSC_ERR_TYPE_INCOMPLETE;
    }

    UINT64 addr = DscReadUnsigned(data, byte_size);

    if (addr == 0) {
        DscStrbufAppend(out, "NULL");
    } else {
        /* Show hex address with pointee type hint if available */
        int digits = (int)(byte_size * 2);
        if (type->u.pointer.pointee && type->u.pointer.pointee->name) {
            DscStrbufAppendf(out, "0x%0*llX /* %s* */",
                               digits, (unsigned long long)addr,
                               type->u.pointer.pointee->name);
        } else if (type->u.pointer.pointee == NULL) {
            DscStrbufAppendf(out, "0x%0*llX /* void* */",
                               digits, (unsigned long long)addr);
        } else {
            DscStrbufAppendf(out, "0x%0*llX",
                               digits, (unsigned long long)addr);
        }
    }

    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Public: format a bitfield value                                     */
/* ------------------------------------------------------------------ */
int DscFormatBitfield(const void *data, UINT32 data_len,
                        const dsc_type_t *type, const DscFormatOpts *opts,
                        DscStrbuf *out)
{
    if (!data || !type || !out) {
        return DSC_ERR_INVALID_ARG;
    }

    /* Read the containing storage unit */
    UINT32 byte_size = type->byte_size;
    if (byte_size == 0) {
        /* Fallback: use base_type size */
        if (type->u.bitfield.base_type) {
            byte_size = type->u.bitfield.base_type->byte_size;
        }
    }
    if (byte_size == 0 || data_len < byte_size) {
        DscStrbufAppend(out, "<incomplete bitfield>");
        return DSC_ERR_TYPE_INCOMPLETE;
    }

    UINT64 raw = DscReadUnsigned(data, byte_size);

    /* Extract the bitfield: shift right by bit_offset, mask to bit_size */
    UINT8 bit_off  = type->u.bitfield.bit_offset;
    UINT8 bit_size = type->u.bitfield.bit_size;

    UINT64 mask = (bit_size >= 64) ? ~(UINT64)0
                                     : ((UINT64)1 << bit_size) - 1;
    UINT64 val = (raw >> bit_off) & mask;

    if (opts->hex_integers) {
        DscStrbufAppendf(out, "0x%llX", (unsigned long long)val);
    } else {
        DscStrbufAppendf(out, "%llu", (unsigned long long)val);
    }
    DscStrbufAppendf(out, " /* bits[%u:%u] */",
                       bit_off, bit_off + bit_size - 1);

    return DSC_OK;
}
