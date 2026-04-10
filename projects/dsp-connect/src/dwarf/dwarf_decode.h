/* PURPOSE: Low-level DWARF decoding helpers — LEB128, abbreviations, attributes
 * PATTERN: Pure functions operating on raw byte pointers, no allocations
 * FOR: Weak AI to reference when parsing binary DWARF data without libdwarf */

#ifndef DSC_DWARF_DECODE_H
#define DSC_DWARF_DECODE_H

#include "../util/types.h"

/* ------------------------------------------------------------------ */
/* DWARF constants — only the subset we actually use                  */
/* ------------------------------------------------------------------ */

/* DW_TAG_* */
#define DW_TAG_array_type        0x01
#define DW_TAG_enumeration_type  0x04
#define DW_TAG_member            0x0d
#define DW_TAG_pointer_type      0x0f
#define DW_TAG_compile_unit      0x11
#define DW_TAG_structure_type    0x13
#define DW_TAG_subroutine_type   0x15
#define DW_TAG_typedef           0x16
#define DW_TAG_union_type        0x17
#define DW_TAG_subrange_type     0x21
#define DW_TAG_base_type         0x24
#define DW_TAG_const_type        0x26
#define DW_TAG_enumerator        0x28
#define DW_TAG_variable          0x34
#define DW_TAG_volatile_type     0x35

/* DW_AT_* */
#define DW_AT_location           0x02
#define DW_AT_name               0x03
#define DW_AT_byte_size          0x0b
#define DW_AT_bit_offset         0x0c
#define DW_AT_bit_size           0x0d
#define DW_AT_const_value        0x1c
#define DW_AT_upper_bound        0x2f
#define DW_AT_count              0x37
#define DW_AT_data_member_location 0x38
#define DW_AT_encoding           0x3e
#define DW_AT_external           0x3f
#define DW_AT_type               0x49

/* DW_ATE_* (base type encodings) */
#define DW_ATE_boolean           0x02
#define DW_ATE_float             0x04
#define DW_ATE_signed            0x05
#define DW_ATE_signed_char       0x06
#define DW_ATE_unsigned          0x07
#define DW_ATE_unsigned_char     0x08

/* DW_FORM_* */
#define DW_FORM_addr             0x01
#define DW_FORM_block1           0x0a
#define DW_FORM_block2           0x03
#define DW_FORM_block4           0x04
#define DW_FORM_data1            0x0b
#define DW_FORM_data2            0x05
#define DW_FORM_data4            0x06
#define DW_FORM_data8            0x07
#define DW_FORM_string           0x08
#define DW_FORM_flag             0x0c
#define DW_FORM_strp             0x0e
#define DW_FORM_udata            0x0f
#define DW_FORM_ref1             0x11
#define DW_FORM_ref2             0x12
#define DW_FORM_ref4             0x13
#define DW_FORM_ref8             0x14
#define DW_FORM_ref_udata        0x15
#define DW_FORM_sdata            0x0d
#define DW_FORM_sec_offset       0x17
#define DW_FORM_exprloc          0x18
#define DW_FORM_flag_present     0x19

/* DW_CHILDREN_* */
#define DW_CHILDREN_no           0x00
#define DW_CHILDREN_yes          0x01

/* ------------------------------------------------------------------ */
/* Abbreviation entry                                                 */
/* ------------------------------------------------------------------ */

#define DWARF_MAX_ATTRS   32
#define DWARF_MAX_ABBREVS 256

typedef struct {
    UINT32 code;
    UINT32 tag;
    int    has_children;
    struct {
        UINT32 name;
        UINT32 form;
    } attrs[DWARF_MAX_ATTRS];
    UINT32 attr_count;
} dwarf_abbrev_t;

/* ------------------------------------------------------------------ */
/* Attribute value (decoded)                                          */
/* ------------------------------------------------------------------ */

typedef struct {
    UINT32      name;       /* DW_AT_* */
    UINT32      form;       /* DW_FORM_* */
    UINT64      uval;       /* unsigned value / offset / address */
    INT64       sval;       /* signed value (for DW_FORM_sdata) */
    const char *str;        /* string pointer (into .debug_str or inline) */
} dwarf_attr_val_t;

/* ------------------------------------------------------------------ */
/* Compilation unit header                                            */
/* ------------------------------------------------------------------ */

typedef struct {
    UINT32      unit_length;
    UINT16      version;
    UINT32      abbrev_offset;
    UINT8       address_size;
    const UINT8 *die_start;    /* pointer to first DIE byte after header */
    const UINT8 *cu_end;       /* pointer past last byte of this CU */
} dwarf_cu_header_t;

/* ------------------------------------------------------------------ */
/* LEB128 decoders                                                    */
/* ------------------------------------------------------------------ */

UINT64 DscDwarfReadUleb128(const UINT8 **p, const UINT8 *end);
INT64  DscDwarfReadSleb128(const UINT8 **p, const UINT8 *end);

/* ------------------------------------------------------------------ */
/* Abbreviation table                                                 */
/* ------------------------------------------------------------------ */

/* Parse .debug_abbrev starting at `offset`. Returns count of entries. */
int DscDwarfParseAbbrevs(const UINT8 *abbrev_data, UINT32 abbrev_size,
                         UINT32 offset,
                         dwarf_abbrev_t *out, UINT32 out_cap);

/* Find abbreviation by code. Returns NULL if not found. */
const dwarf_abbrev_t *DscDwarfFindAbbrev(const dwarf_abbrev_t *table,
                                         int count, UINT32 code);

/* ------------------------------------------------------------------ */
/* CU header                                                          */
/* ------------------------------------------------------------------ */

/* Parse a CU header. Returns 0 on success, -1 on error. */
int DscDwarfParseCuHeader(const UINT8 *data, UINT32 size,
                          dwarf_cu_header_t *out);

/* ------------------------------------------------------------------ */
/* Attribute reading                                                  */
/* ------------------------------------------------------------------ */

/* Read one attribute value, advancing *p. Returns 0 on success, -1 on
 * unknown form (caller should skip the DIE). */
int DscDwarfReadAttr(const UINT8 **p, const UINT8 *end,
                     UINT32 attr_name, UINT32 form,
                     UINT8 address_size,
                     const UINT8 *debug_str, UINT32 debug_str_size,
                     dwarf_attr_val_t *out);

/* Skip one attribute value by form (when we don't care about the value).
 * Returns 0 on success, -1 on unknown form. */
int DscDwarfSkipAttr(const UINT8 **p, const UINT8 *end,
                     UINT32 form, UINT8 address_size);

/* ------------------------------------------------------------------ */
/* DIE-level attribute reading                                        */
/* ------------------------------------------------------------------ */

/* Read all attributes of a DIE per its abbreviation. Returns attribute
 * count on success, -1 on error (unknown form). */
int DscDwarfReadDieAttrs(const UINT8 **p, const UINT8 *end,
                         const dwarf_abbrev_t *abbrev,
                         UINT8 addr_size,
                         const UINT8 *debug_str, UINT32 str_size,
                         dwarf_attr_val_t *out, UINT32 out_cap);

/* ------------------------------------------------------------------ */
/* Attribute value extraction helpers                                 */
/* ------------------------------------------------------------------ */

/* Find a named attribute in a decoded array. Returns NULL if not found. */
const dwarf_attr_val_t *DscDwarfFindAttr(const dwarf_attr_val_t *attrs,
                                         UINT32 count, UINT32 name);

/* Get string value, or NULL */
const char *DscDwarfAttrStr(const dwarf_attr_val_t *attrs,
                            UINT32 count, UINT32 name);

/* Get unsigned value, or `def` if not found */
UINT64 DscDwarfAttrUint(const dwarf_attr_val_t *attrs,
                        UINT32 count, UINT32 name, UINT64 def);

/* Get signed value, or `def` if not found */
INT64 DscDwarfAttrSint(const dwarf_attr_val_t *attrs,
                       UINT32 count, UINT32 name, INT64 def);

/* Get DW_AT_type reference as section-global offset, or 0 */
UINT64 DscDwarfAttrTypeRef(const dwarf_attr_val_t *attrs,
                           UINT32 count, UINT64 cu_base);

#endif /* DSC_DWARF_DECODE_H */
