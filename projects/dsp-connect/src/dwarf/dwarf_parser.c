/* PURPOSE: DWARF parser — reads ELF .debug_info/.debug_abbrev/.debug_str
 *          directly, no libdwarf dependency
 * PATTERN: Two-pass parse: (1) build types + collect refs, (2) resolve refs.
 *          Hashmap-based type cache keyed by DIE offset.
 * FOR: Weak AI to reference when implementing ELF/DWARF debug info extraction */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "dwarf_parser.h"
#include "dwarf_decode.h"
#include "elf_reader.h"
#include "../core/dsc_errors.h"
#include "../util/hashmap.h"
#include "../util/log.h"

/* ------------------------------------------------------------------ */
/* Internal state                                                     */
/* ------------------------------------------------------------------ */

#define TYPE_POOL_INITIAL_CAP 256
#define MAX_PENDING_REFS      1024

typedef struct {
    dsc_type_t **target;     /* slot to fill with resolved type ptr */
    UINT64       die_offset; /* DIE offset of the referenced type */
} pending_ref_t;

struct dsc_dwarf {
    char           *elf_path;
    elf_file_t      elf;
    dsc_type_t    **types;
    UINT32          type_count;
    UINT32          type_cap;
    DscHashmap      type_index;    /* DIE offset -> dsc_type_t* */
    pending_ref_t  *pending_refs;
    UINT32          pending_count;
    UINT32          pending_cap;
    int             symbols_loaded;
};

/* ------------------------------------------------------------------ */
/* Type pool + index helpers                                          */
/* ------------------------------------------------------------------ */

static int pool_add(dsc_dwarf_t *dw, dsc_type_t *type)
{
    if (dw->type_count >= dw->type_cap) {
        UINT32 new_cap = dw->type_cap * 2;
        dsc_type_t **buf = realloc(dw->types, new_cap * sizeof(*buf));
        if (!buf) { return DSC_ERR_NOMEM; }
        dw->types    = buf;
        dw->type_cap = new_cap;
    }
    dw->types[dw->type_count++] = type;
    return DSC_OK;
}

static int index_type(dsc_dwarf_t *dw, dsc_type_t *type)
{
    char key[21];
    snprintf(key, sizeof(key), "%llu", (unsigned long long)type->die_offset);
    return DscHashmapPut(&dw->type_index, key, type);
}

static dsc_type_t *alloc_type(dsc_type_kind_t kind, UINT64 die_offset)
{
    dsc_type_t *t = calloc(1, sizeof(dsc_type_t));
    if (!t) { return NULL; }
    t->kind       = kind;
    t->die_offset = die_offset;
    return t;
}

static int add_pending_ref(dsc_dwarf_t *dw, dsc_type_t **target, UINT64 off)
{
    if (dw->pending_count >= dw->pending_cap) {
        UINT32 new_cap = dw->pending_cap * 2;
        pending_ref_t *buf = realloc(dw->pending_refs, new_cap * sizeof(*buf));
        if (!buf) { return DSC_ERR_NOMEM; }
        dw->pending_refs = buf;
        dw->pending_cap  = new_cap;
    }
    dw->pending_refs[dw->pending_count].target     = target;
    dw->pending_refs[dw->pending_count].die_offset = off;
    dw->pending_count++;
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Tag / encoding mapping                                             */
/* ------------------------------------------------------------------ */

static dsc_type_kind_t tag_to_kind(UINT32 tag)
{
    switch (tag) {
    case DW_TAG_base_type:        return DSC_TYPE_BASE;
    case DW_TAG_structure_type:   return DSC_TYPE_STRUCT;
    case DW_TAG_union_type:       return DSC_TYPE_UNION;
    case DW_TAG_pointer_type:     return DSC_TYPE_POINTER;
    case DW_TAG_typedef:          return DSC_TYPE_TYPEDEF;
    case DW_TAG_const_type:       return DSC_TYPE_CONST;
    case DW_TAG_volatile_type:    return DSC_TYPE_VOLATILE;
    case DW_TAG_array_type:       return DSC_TYPE_ARRAY;
    case DW_TAG_enumeration_type: return DSC_TYPE_ENUM;
    case DW_TAG_subroutine_type:  return DSC_TYPE_FUNC;
    default:                      return DSC_TYPE_KIND_COUNT;
    }
}

static dsc_base_encoding_t translate_encoding(UINT64 ate)
{
    switch (ate) {
    case DW_ATE_signed:        return DSC_ENC_SIGNED;
    case DW_ATE_signed_char:   return DSC_ENC_CHAR;
    case DW_ATE_unsigned:      return DSC_ENC_UNSIGNED;
    case DW_ATE_unsigned_char: return DSC_ENC_CHAR;
    case DW_ATE_float:         return DSC_ENC_FLOAT;
    case DW_ATE_boolean:       return DSC_ENC_BOOL;
    default:                   return DSC_ENC_UNSIGNED;
    }
}

/* ------------------------------------------------------------------ */
/* Type builder: select the correct pending-ref slot for DW_AT_type   */
/* ------------------------------------------------------------------ */

static dsc_type_t **ref_slot_for(dsc_type_t *t, dsc_type_kind_t kind)
{
    if (kind == DSC_TYPE_POINTER) { return &t->u.pointer.pointee; }
    if (kind == DSC_TYPE_TYPEDEF || kind == DSC_TYPE_CONST
        || kind == DSC_TYPE_VOLATILE) { return &t->u.modifier.target; }
    if (kind == DSC_TYPE_ARRAY)   { return &t->u.array.element_type; }
    if (kind == DSC_TYPE_ENUM)    { return &t->u.enumeration.underlying; }
    return NULL;
}

static dsc_type_t *build_type(dsc_dwarf_t *dw, UINT32 tag, UINT64 die_off,
                              const dwarf_attr_val_t *a, UINT32 ac,
                              UINT64 cu_off)
{
    dsc_type_kind_t kind = tag_to_kind(tag);
    if (kind == DSC_TYPE_KIND_COUNT) { return NULL; }

    dsc_type_t *t = alloc_type(kind, die_off);
    if (!t) { return NULL; }

    const char *name = DscDwarfAttrStr(a, ac, DW_AT_name);
    t->name      = name ? strdup(name) : NULL;
    t->byte_size = (UINT32)DscDwarfAttrUint(a, ac, DW_AT_byte_size, 0);
    if (tag == DW_TAG_base_type) {
        t->u.base.encoding = translate_encoding(
            DscDwarfAttrUint(a, ac, DW_AT_encoding, 0));
    }

    UINT64 ref = DscDwarfAttrTypeRef(a, ac, cu_off);
    if (ref != 0) {
        dsc_type_t **slot = ref_slot_for(t, kind);
        if (slot) { add_pending_ref(dw, slot, ref); }
    }

    pool_add(dw, t);
    index_type(dw, t);
    return t;
}

/* ------------------------------------------------------------------ */
/* Child DIE handlers                                                 */
/* ------------------------------------------------------------------ */

static void handle_member(dsc_dwarf_t *dw, dsc_type_t *parent,
                          const dwarf_attr_val_t *a, UINT32 ac, UINT64 cu)
{
    if (!parent || (parent->kind != DSC_TYPE_STRUCT
                    && parent->kind != DSC_TYPE_UNION)) { return; }

    UINT32 fc = parent->u.composite.field_count;
    dsc_struct_field_t *f = realloc(parent->u.composite.fields,
                                    (fc + 1) * sizeof(*f));
    if (!f) { return; }
    parent->u.composite.fields = f;
    memset(&f[fc], 0, sizeof(f[fc]));

    const char *name = DscDwarfAttrStr(a, ac, DW_AT_name);
    f[fc].name        = name ? strdup(name) : NULL;
    f[fc].byte_offset = (UINT32)DscDwarfAttrUint(a, ac, DW_AT_data_member_location, 0);
    f[fc].bit_offset  = (UINT8)DscDwarfAttrUint(a, ac, DW_AT_bit_offset, 0);
    f[fc].bit_size    = (UINT8)DscDwarfAttrUint(a, ac, DW_AT_bit_size, 0);

    UINT64 ref = DscDwarfAttrTypeRef(a, ac, cu);
    if (ref != 0) { add_pending_ref(dw, &f[fc].type, ref); }
    parent->u.composite.field_count = fc + 1;
}

static void handle_enumerator(dsc_type_t *parent,
                              const dwarf_attr_val_t *a, UINT32 ac)
{
    if (!parent || parent->kind != DSC_TYPE_ENUM) { return; }

    UINT32 vc = parent->u.enumeration.value_count;
    dsc_enum_value_t *v = realloc(parent->u.enumeration.values,
                                  (vc + 1) * sizeof(*v));
    if (!v) { return; }
    parent->u.enumeration.values = v;

    const char *name = DscDwarfAttrStr(a, ac, DW_AT_name);
    v[vc].name  = name ? strdup(name) : NULL;
    v[vc].value = DscDwarfAttrSint(a, ac, DW_AT_const_value, 0);
    parent->u.enumeration.value_count = vc + 1;
}

static void handle_subrange(dsc_type_t *parent,
                            const dwarf_attr_val_t *a, UINT32 ac)
{
    if (!parent || parent->kind != DSC_TYPE_ARRAY) { return; }

    UINT32 dc = parent->u.array.dim_count;
    dsc_array_dim_t *d = realloc(parent->u.array.dims,
                                 (dc + 1) * sizeof(*d));
    if (!d) { return; }
    parent->u.array.dims = d;

    d[dc].lower_bound = 0;
    UINT64 upper = DscDwarfAttrUint(a, ac, DW_AT_upper_bound, 0);
    UINT64 cnt   = DscDwarfAttrUint(a, ac, DW_AT_count, 0);
    d[dc].count  = cnt ? (UINT32)cnt : (UINT32)(upper + 1);
    parent->u.array.dim_count = dc + 1;
}

/* ------------------------------------------------------------------ */
/* Variable collection                                                */
/* ------------------------------------------------------------------ */

static void collect_variable(dsc_dwarf_t *dw, dsc_symtab_t *tab,
                             const dwarf_attr_val_t *a, UINT32 ac,
                             UINT64 cu)
{
    const char *name = DscDwarfAttrStr(a, ac, DW_AT_name);
    if (!name) {
        return;
    }

    UINT64 addr = DscDwarfAttrUint(a, ac, DW_AT_location, 0);
    int ext = (int)DscDwarfAttrUint(a, ac, DW_AT_external, 0);

    /* 先添加符号（type=NULL），记录索引以便第二遍 resolve */
    UINT32 sym_idx = tab->count;
    dsc_symtab_add(tab, name, addr, 0, NULL, ext != 0);

    /* 把类型引用加入 pending，指向刚添加的符号的 type 字段 */
    UINT64 ref = DscDwarfAttrTypeRef(a, ac, cu);
    if (ref != 0 && sym_idx < tab->count) {
        add_pending_ref(dw, &tab->symbols[sym_idx].type, ref);
    }
}

/* ------------------------------------------------------------------ */
/* Single CU traversal                                                */
/* ------------------------------------------------------------------ */

static void dispatch_die(dsc_dwarf_t *dw, UINT32 tag, UINT64 die_off,
                         const dwarf_attr_val_t *a, UINT32 ac,
                         UINT64 cu_off, dsc_type_t *parent,
                         dsc_symtab_t *tab, dsc_type_t **built_out)
{
    *built_out = NULL;
    if (tag_to_kind(tag) != DSC_TYPE_KIND_COUNT) {
        *built_out = build_type(dw, tag, die_off, a, ac, cu_off);
    } else if (tag == DW_TAG_member) {
        handle_member(dw, parent, a, ac, cu_off);
    } else if (tag == DW_TAG_enumerator) {
        handle_enumerator(parent, a, ac);
    } else if (tag == DW_TAG_subrange_type) {
        handle_subrange(parent, a, ac);
    } else if (tag == DW_TAG_variable && tab) {
        collect_variable(dw, tab, a, ac, cu_off);
    }
}

static int parse_cu(dsc_dwarf_t *dw, const dwarf_cu_header_t *cu,
                    const dwarf_abbrev_t *abbrevs, int abbrev_count,
                    const UINT8 *debug_str, UINT32 str_size,
                    UINT64 cu_off, const UINT8 *sec_base, dsc_symtab_t *tab)
{
    const UINT8 *p = cu->die_start;
    const UINT8 *end = cu->cu_end;
    dsc_type_t *pstack[64];
    int dstack[64];
    int sp = 0, depth = 0;

    while (p < end) {
        UINT64 die_off = (UINT64)(p - sec_base);
        UINT64 code = DscDwarfReadUleb128(&p, end);
        if (code == 0) {
            depth--;
            if (sp > 0 && dstack[sp - 1] >= depth) { sp--; }
            continue;
        }
        const dwarf_abbrev_t *ab = DscDwarfFindAbbrev(
            abbrevs, abbrev_count, (UINT32)code);
        if (!ab) {
            DSC_LOG_WARN("unknown abbrev code %u", (unsigned)code);
            return DSC_ERR_DWARF_PARSE;
        }
        dwarf_attr_val_t attrs[DWARF_MAX_ATTRS];
        int ac = DscDwarfReadDieAttrs(&p, end, ab, cu->address_size,
                                      debug_str, str_size,
                                      attrs, DWARF_MAX_ATTRS);
        if (ac < 0) {
            DSC_LOG_WARN("unknown form at DIE offset %llu",
                         (unsigned long long)die_off);
            return DSC_ERR_DWARF_PARSE;
        }
        dsc_type_t *par = (sp > 0) ? pstack[sp - 1] : NULL;
        dsc_type_t *built = NULL;
        dispatch_die(dw, ab->tag, die_off, attrs, (UINT32)ac,
                     cu_off, par, tab, &built);
        if (ab->has_children) {
            if (built && sp < 64) {
                pstack[sp] = built;
                dstack[sp] = depth;
                sp++;
            }
            depth++;
        }
    }
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Reference resolution + full parse                                  */
/* ------------------------------------------------------------------ */

static void resolve_pending_refs(dsc_dwarf_t *dw)
{
    for (UINT32 i = 0; i < dw->pending_count; i++) {
        char key[21];
        snprintf(key, sizeof(key), "%llu",
                 (unsigned long long)dw->pending_refs[i].die_offset);
        dsc_type_t *t = DscHashmapGet(&dw->type_index, key);
        if (t) { *(dw->pending_refs[i].target) = t; }
    }
}

static int parse_all_cus(dsc_dwarf_t *dw, dsc_symtab_t *tab)
{
    const elf_section_t *info = elf_find_section(&dw->elf, ".debug_info");
    const elf_section_t *abbr = elf_find_section(&dw->elf, ".debug_abbrev");
    if (!info || !abbr) { return DSC_ERR_DWARF_NO_DEBUG; }

    const elf_section_t *ss = elf_find_section(&dw->elf, ".debug_str");
    const UINT8 *dstr = ss ? ss->data : NULL;
    UINT32 stsz       = ss ? ss->size : 0;
    const UINT8 *p    = info->data;
    const UINT8 *end  = info->data + info->size;

    while (p < end) {
        UINT64 cu_off = (UINT64)(p - info->data);
        dwarf_cu_header_t cu;
        if (DscDwarfParseCuHeader(p, (UINT32)(end - p), &cu) < 0) {
            DSC_LOG_WARN("bad CU header at %llu", (unsigned long long)cu_off);
            break;
        }
        dwarf_abbrev_t ab[DWARF_MAX_ABBREVS];
        int abc = DscDwarfParseAbbrevs(abbr->data, abbr->size,
                                       cu.abbrev_offset, ab, DWARF_MAX_ABBREVS);
        dwarf_cu_header_t fc = cu;
        fc.die_start = p + 11;
        fc.cu_end    = p + 4 + cu.unit_length;
        if (fc.cu_end > end) { fc.cu_end = end; }
        parse_cu(dw, &fc, ab, abc, dstr, stsz, cu_off, info->data, tab);
        p = fc.cu_end;
    }
    resolve_pending_refs(dw);
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Public API                                                         */
/* ------------------------------------------------------------------ */

dsc_dwarf_t *dsc_dwarf_open(const char *elf_path, int *err_out)
{
    if (!elf_path) {
        if (err_out) { *err_out = DSC_ERR_INVALID_ARG; }
        return NULL;
    }
    dsc_dwarf_t *dw = calloc(1, sizeof(*dw));
    if (!dw) {
        if (err_out) { *err_out = DSC_ERR_NOMEM; }
        return NULL;
    }
    if (elf_open(&dw->elf, elf_path) != 0) {
        free(dw);
        if (err_out) { *err_out = DSC_ERR_ELF_OPEN; }
        return NULL;
    }
    dw->elf_path     = strdup(elf_path);
    dw->types        = calloc(TYPE_POOL_INITIAL_CAP, sizeof(dsc_type_t *));
    dw->type_cap     = TYPE_POOL_INITIAL_CAP;
    dw->pending_refs = calloc(MAX_PENDING_REFS, sizeof(pending_ref_t));
    dw->pending_cap  = MAX_PENDING_REFS;
    DscHashmapInit(&dw->type_index, TYPE_POOL_INITIAL_CAP);

    int rc = parse_all_cus(dw, NULL);
    if (rc < 0) {
        DSC_LOG_WARN("DWARF parse returned %d for '%s'", rc, elf_path);
    }
    DSC_LOG_INFO("parsed %u types from '%s'", dw->type_count, elf_path);
    if (err_out) { *err_out = DSC_OK; }
    return dw;
}

void dsc_dwarf_close(dsc_dwarf_t *dw)
{
    if (!dw) { return; }
    for (UINT32 i = 0; i < dw->type_count; i++) {
        dsc_type_free(dw->types[i]);
    }
    free(dw->types);
    free(dw->pending_refs);
    DscHashmapFree(&dw->type_index);
    elf_close(&dw->elf);
    free(dw->elf_path);
    free(dw);
}

int dsc_dwarf_load_symbols(dsc_dwarf_t *dw, dsc_symtab_t *tab)
{
    if (!dw || !tab) { return DSC_ERR_INVALID_ARG; }
    if (dw->symbols_loaded) { return DSC_OK; }
    int rc = parse_all_cus(dw, tab);
    dw->symbols_loaded = 1;
    DSC_LOG_INFO("loaded %u symbols", dsc_symtab_count(tab));
    return rc;
}

const dsc_type_t *dsc_dwarf_lookup_type(dsc_dwarf_t *dw, UINT64 die_offset)
{
    if (!dw) { return NULL; }
    char key[21];
    snprintf(key, sizeof(key), "%llu", (unsigned long long)die_offset);
    return (const dsc_type_t *)DscHashmapGet(&dw->type_index, key);
}

const char *dsc_dwarf_path(const dsc_dwarf_t *dw)
{
    return dw ? dw->elf_path : NULL;
}
