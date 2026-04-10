/* PURPOSE: Low-level DWARF decoding — LEB128, abbreviations, attribute values
 * PATTERN: Pure byte-pointer functions, no heap allocation, bounds-checked
 * FOR: Weak AI to reference when decoding DWARF binary data by hand */

#include <string.h>

#include "dwarf_decode.h"
#include "../util/log.h"

/* ------------------------------------------------------------------ */
/* Byte readers (little-endian, bounds-checked)                       */
/* ------------------------------------------------------------------ */

static UINT16 read_u16(const UINT8 **p, const UINT8 *end)
{
    if (*p + 2 > end) {
        return 0;
    }
    UINT16 v = (UINT16)((*p)[0] | ((*p)[1] << 8));
    *p += 2;
    return v;
}

static UINT32 read_u32(const UINT8 **p, const UINT8 *end)
{
    if (*p + 4 > end) {
        return 0;
    }
    UINT32 v = (UINT32)((*p)[0])
             | ((UINT32)((*p)[1]) << 8)
             | ((UINT32)((*p)[2]) << 16)
             | ((UINT32)((*p)[3]) << 24);
    *p += 4;
    return v;
}

static UINT64 read_u64(const UINT8 **p, const UINT8 *end)
{
    if (*p + 8 > end) {
        return 0;
    }
    UINT64 lo = read_u32(p, end);
    UINT64 hi = read_u32(p, end);
    return lo | (hi << 32);
}

/* ------------------------------------------------------------------ */
/* LEB128 decoders                                                    */
/* ------------------------------------------------------------------ */

UINT64 DscDwarfReadUleb128(const UINT8 **p, const UINT8 *end)
{
    UINT64 result = 0;
    UINT32 shift = 0;

    while (*p < end) {
        UINT8 byte = **p;
        (*p)++;
        result |= (UINT64)(byte & 0x7F) << shift;
        if ((byte & 0x80) == 0) {
            break;
        }
        shift += 7;
    }
    return result;
}

INT64 DscDwarfReadSleb128(const UINT8 **p, const UINT8 *end)
{
    INT64 result = 0;
    UINT32 shift = 0;
    UINT8 byte = 0;

    while (*p < end) {
        byte = **p;
        (*p)++;
        result |= (INT64)(byte & 0x7F) << shift;
        shift += 7;
        if ((byte & 0x80) == 0) {
            break;
        }
    }
    /* Sign extend if high bit of last byte was set */
    if ((shift < 64) && (byte & 0x40)) {
        result |= -(((INT64)1) << shift);
    }
    return result;
}

/* ------------------------------------------------------------------ */
/* Abbreviation table parsing                                         */
/* ------------------------------------------------------------------ */

/* Parse one abbreviation entry. Returns 0 on success, 1 at terminator,
 * -1 on error. */
static int parse_one_abbrev(const UINT8 **p, const UINT8 *end,
                            dwarf_abbrev_t *out)
{
    out->code = (UINT32)DscDwarfReadUleb128(p, end);
    if (out->code == 0) {
        return 1; /* terminator */
    }

    out->tag = (UINT32)DscDwarfReadUleb128(p, end);
    if (*p >= end) {
        return -1;
    }
    out->has_children = (**p == DW_CHILDREN_yes) ? 1 : 0;
    (*p)++;
    out->attr_count = 0;

    while (*p < end) {
        UINT32 name = (UINT32)DscDwarfReadUleb128(p, end);
        UINT32 form = (UINT32)DscDwarfReadUleb128(p, end);
        if (name == 0 && form == 0) {
            break; /* end of attr list */
        }
        if (out->attr_count < DWARF_MAX_ATTRS) {
            out->attrs[out->attr_count].name = name;
            out->attrs[out->attr_count].form = form;
            out->attr_count++;
        }
    }
    return 0;
}

int DscDwarfParseAbbrevs(const UINT8 *abbrev_data, UINT32 abbrev_size,
                         UINT32 offset,
                         dwarf_abbrev_t *out, UINT32 out_cap)
{
    if (offset >= abbrev_size) {
        return 0;
    }
    const UINT8 *p = abbrev_data + offset;
    const UINT8 *end = abbrev_data + abbrev_size;
    int count = 0;

    while (p < end && (UINT32)count < out_cap) {
        int rc = parse_one_abbrev(&p, end, &out[count]);
        if (rc == 1) {
            break; /* terminator */
        }
        if (rc < 0) {
            DSC_LOG_WARN("malformed abbreviation at index %d", count);
            break;
        }
        count++;
    }
    return count;
}

const dwarf_abbrev_t *DscDwarfFindAbbrev(const dwarf_abbrev_t *table,
                                         int count, UINT32 code)
{
    for (int i = 0; i < count; i++) {
        if (table[i].code == code) {
            return &table[i];
        }
    }
    return NULL;
}

/* ------------------------------------------------------------------ */
/* CU header parsing                                                  */
/* ------------------------------------------------------------------ */

int DscDwarfParseCuHeader(const UINT8 *data, UINT32 size,
                          dwarf_cu_header_t *out)
{
    if (size < 11) {
        return -1; /* minimum: 4 + 2 + 4 + 1 = 11 bytes */
    }
    const UINT8 *p = data;
    const UINT8 *end = data + size;

    out->unit_length   = read_u32(&p, end);
    out->version       = read_u16(&p, end);
    out->abbrev_offset = read_u32(&p, end);
    out->address_size  = *p;
    p++;

    out->die_start = p;
    /* unit_length counts bytes after itself (4-byte length field) */
    out->cu_end = data + 4 + out->unit_length;
    if (out->cu_end > end) {
        out->cu_end = end;
    }
    return 0;
}

/* ------------------------------------------------------------------ */
/* Attribute value reading                                            */
/* ------------------------------------------------------------------ */

/* Read a block: `len_bytes` byte length prefix, then that many data bytes */
static int read_block(const UINT8 **p, const UINT8 *end,
                      UINT32 len_bytes, dwarf_attr_val_t *out)
{
    UINT32 len = 0;
    if (len_bytes == 1 && *p < end) {
        len = **p; (*p)++;
    } else if (len_bytes == 2) {
        len = read_u16(p, end);
    } else if (len_bytes == 4) {
        len = read_u32(p, end);
    }
    out->uval = len;
    if (*p + len > end) {
        return -1;
    }
    *p += len;
    return 0;
}

/* Read a fixed-size unsigned integer, advancing *p */
static UINT64 read_fixed_uint(const UINT8 **p, const UINT8 *end,
                              UINT32 nbytes)
{
    if (nbytes == 1 && *p < end) {
        UINT64 v = **p; (*p)++; return v;
    }
    if (nbytes == 2) {
        return read_u16(p, end);
    }
    if (nbytes == 4) {
        return read_u32(p, end);
    }
    if (nbytes == 8) {
        return read_u64(p, end);
    }
    return 0;
}

/* Read fixed-size and reference forms. Returns 1 if handled, 0 if not. */
static int read_fixed_form(const UINT8 **p, const UINT8 *end,
                           UINT32 form, UINT8 addr_size,
                           dwarf_attr_val_t *out)
{
    switch (form) {
    case DW_FORM_addr:
        out->uval = read_fixed_uint(p, end, addr_size); return 1;
    case DW_FORM_data1: case DW_FORM_ref1: case DW_FORM_flag:
        out->uval = read_fixed_uint(p, end, 1); return 1;
    case DW_FORM_data2: case DW_FORM_ref2:
        out->uval = read_fixed_uint(p, end, 2); return 1;
    case DW_FORM_data4: case DW_FORM_ref4: case DW_FORM_sec_offset:
        out->uval = read_fixed_uint(p, end, 4); return 1;
    case DW_FORM_data8: case DW_FORM_ref8:
        out->uval = read_fixed_uint(p, end, 8); return 1;
    default:
        return 0;
    }
}

/* Read variable-length forms (strings, LEB128, blocks, exprloc).
 * Returns 0 on success, 1 if not handled, -1 on error. */
static int read_varlen_form(const UINT8 **p, const UINT8 *end,
                            UINT32 form,
                            const UINT8 *debug_str, UINT32 str_size,
                            dwarf_attr_val_t *out)
{
    switch (form) {
    case DW_FORM_strp:
        out->uval = read_u32(p, end);
        if (debug_str && out->uval < str_size) {
            out->str = (const char *)(debug_str + out->uval);
        }
        return 0;
    case DW_FORM_string:
        out->str = (const char *)*p;
        while (*p < end && **p != '\0') { (*p)++; }
        if (*p < end) { (*p)++; }
        return 0;
    case DW_FORM_udata: case DW_FORM_ref_udata:
        out->uval = DscDwarfReadUleb128(p, end); return 0;
    case DW_FORM_sdata:
        out->sval = DscDwarfReadSleb128(p, end); return 0;
    case DW_FORM_flag_present:
        out->uval = 1; return 0;
    case DW_FORM_exprloc: {
        UINT64 len = DscDwarfReadUleb128(p, end);
        if (*p + len > end) { return -1; }
        out->uval = len; *p += len; return 0;
    }
    case DW_FORM_block1: return read_block(p, end, 1, out) < 0 ? -1 : 0;
    case DW_FORM_block2: return read_block(p, end, 2, out) < 0 ? -1 : 0;
    case DW_FORM_block4: return read_block(p, end, 4, out) < 0 ? -1 : 0;
    default:
        return 1; /* not handled */
    }
}

int DscDwarfReadAttr(const UINT8 **p, const UINT8 *end,
                     UINT32 attr_name, UINT32 form,
                     UINT8 address_size,
                     const UINT8 *debug_str, UINT32 debug_str_size,
                     dwarf_attr_val_t *out)
{
    memset(out, 0, sizeof(*out));
    out->name = attr_name;
    out->form = form;

    if (read_fixed_form(p, end, form, address_size, out)) {
        return 0;
    }
    int rc = read_varlen_form(p, end, form, debug_str, debug_str_size, out);
    if (rc == 0) { return 0; }
    if (rc < 0)  { return -1; }
    DSC_LOG_WARN("unknown DW_FORM 0x%x for attr 0x%x", form, attr_name);
    return -1;
}

int DscDwarfSkipAttr(const UINT8 **p, const UINT8 *end,
                     UINT32 form, UINT8 address_size)
{
    dwarf_attr_val_t dummy;
    return DscDwarfReadAttr(p, end, 0, form, address_size,
                            NULL, 0, &dummy);
}

/* ------------------------------------------------------------------ */
/* DIE-level attribute reading                                        */
/* ------------------------------------------------------------------ */

int DscDwarfReadDieAttrs(const UINT8 **p, const UINT8 *end,
                         const dwarf_abbrev_t *abbrev,
                         UINT8 addr_size,
                         const UINT8 *debug_str, UINT32 str_size,
                         dwarf_attr_val_t *out, UINT32 out_cap)
{
    UINT32 count = 0;
    for (UINT32 i = 0; i < abbrev->attr_count; i++) {
        UINT32 aname = abbrev->attrs[i].name;
        UINT32 aform = abbrev->attrs[i].form;
        if (count < out_cap) {
            int rc = DscDwarfReadAttr(p, end, aname, aform, addr_size,
                                      debug_str, str_size, &out[count]);
            if (rc < 0) {
                return -1;
            }
            count++;
        } else {
            if (DscDwarfSkipAttr(p, end, aform, addr_size) < 0) {
                return -1;
            }
        }
    }
    return (int)count;
}

/* ------------------------------------------------------------------ */
/* Attribute value extraction helpers                                 */
/* ------------------------------------------------------------------ */

const dwarf_attr_val_t *DscDwarfFindAttr(const dwarf_attr_val_t *attrs,
                                         UINT32 count, UINT32 name)
{
    for (UINT32 i = 0; i < count; i++) {
        if (attrs[i].name == name) {
            return &attrs[i];
        }
    }
    return NULL;
}

const char *DscDwarfAttrStr(const dwarf_attr_val_t *attrs,
                            UINT32 count, UINT32 name)
{
    const dwarf_attr_val_t *a = DscDwarfFindAttr(attrs, count, name);
    return (a && a->str) ? a->str : NULL;
}

UINT64 DscDwarfAttrUint(const dwarf_attr_val_t *attrs,
                        UINT32 count, UINT32 name, UINT64 def)
{
    const dwarf_attr_val_t *a = DscDwarfFindAttr(attrs, count, name);
    return a ? a->uval : def;
}

INT64 DscDwarfAttrSint(const dwarf_attr_val_t *attrs,
                       UINT32 count, UINT32 name, INT64 def)
{
    const dwarf_attr_val_t *a = DscDwarfFindAttr(attrs, count, name);
    if (!a) {
        return def;
    }
    return (a->form == DW_FORM_sdata) ? a->sval : (INT64)a->uval;
}

UINT64 DscDwarfAttrTypeRef(const dwarf_attr_val_t *attrs,
                           UINT32 count, UINT64 cu_base)
{
    const dwarf_attr_val_t *a = DscDwarfFindAttr(attrs, count, DW_AT_type);
    if (!a) {
        return 0;
    }
    return cu_base + a->uval;
}
