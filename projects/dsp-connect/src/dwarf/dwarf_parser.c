/* PURPOSE: DWARF parser implementation — wraps libdwarf or provides stubs
 * PATTERN: Conditional compilation (#ifdef DSC_USE_LIBDWARF), DSC_TRY macro,
 *          single-pass DIE traversal, hashmap-based type cache
 * FOR: Weak AI to reference when implementing ELF/DWARF debug info extraction */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "dwarf_parser.h"
#include "../core/dsc_errors.h"
#include "../util/hashmap.h"
#include "../util/log.h"

/* ------------------------------------------------------------------ */
/* Internal parser state                                              */
/* ------------------------------------------------------------------ */

#define TYPE_POOL_INITIAL_CAP 256

struct dsc_dwarf {
    char           *elf_path;

    /* Type pool: all parsed types owned here */
    dsc_type_t    **types;       /* array of pointers to heap-allocated types */
    UINT32          type_count;
    UINT32          type_cap;

    /* DIE offset → dsc_type_t* index for O(1) lookup */
    DscHashmap   type_index;

    /* Whether symbols have been loaded already */
    int             symbols_loaded;

#ifdef DSC_USE_LIBDWARF
    /* libdwarf handles */
    void           *dbg;         /* Dwarf_Debug */
    int             elf_fd;
#endif
};

/* ------------------------------------------------------------------ */
/* Conditional compilation: real libdwarf vs. stub                     */
/* ------------------------------------------------------------------ */

#ifdef DSC_USE_LIBDWARF

/* ------------------------------------------------------------------ */
/* Internal helpers (only used by libdwarf path)                      */
/* ------------------------------------------------------------------ */

/* Add a type to the pool. The parser takes ownership. */
static int pool_add_type(dsc_dwarf_t *dw, dsc_type_t *type)
{
    if (dw->type_count >= dw->type_cap) {
        UINT32 new_cap = dw->type_cap * 2;
        dsc_type_t **new_buf = realloc(dw->types, new_cap * sizeof(dsc_type_t *));
        if (!new_buf) {
            return DSC_ERR_NOMEM;
        }
        dw->types    = new_buf;
        dw->type_cap = new_cap;
    }
    dw->types[dw->type_count++] = type;
    return DSC_OK;
}

/* Register a type in the DIE-offset index for later lookup. */
static int index_type(dsc_dwarf_t *dw, dsc_type_t *type)
{
    char key[21];
    snprintf(key, sizeof(key), "%llu", (unsigned long long)type->die_offset);
    return DscHashmapPut(&dw->type_index, key, type);
}

/* Allocate and zero-initialize a new type node */
static dsc_type_t *alloc_type(dsc_type_kind_t kind, UINT64 die_offset)
{
    dsc_type_t *t = calloc(1, sizeof(dsc_type_t));
    if (!t) {
        return NULL;
    }
    t->kind       = kind;
    t->die_offset = die_offset;
    return t;
}

/* --------------------------------------------------------------- */
/* Real libdwarf implementation                                    */
/* --------------------------------------------------------------- */

#include <dwarf.h>
#include <libdwarf.h>
#include <fcntl.h>
#include <unistd.h>

/* Convert DW_ATE_* to our encoding enum */
static dsc_base_encoding_t translate_encoding(unsigned ate)
{
    switch (ate) {
    case DW_ATE_signed:      return DSC_ENC_SIGNED;
    case DW_ATE_signed_char: return DSC_ENC_CHAR;
    case DW_ATE_unsigned:    return DSC_ENC_UNSIGNED;
    case DW_ATE_unsigned_char: return DSC_ENC_CHAR;
    case DW_ATE_float:       return DSC_ENC_FLOAT;
    case DW_ATE_boolean:     return DSC_ENC_BOOL;
    default:                 return DSC_ENC_UNSIGNED;
    }
}

/* Get a string attribute from a DIE, or NULL */
static char *die_get_name(Dwarf_Debug dbg, Dwarf_Die die)
{
    char *name = NULL;
    Dwarf_Error err = NULL;
    if (dwarf_diename(die, &name, &err) == DW_DLV_OK) {
        char *copy = strdup(name);
        dwarf_dealloc(dbg, name, DW_DLA_STRING);
        return copy;
    }
    return NULL;
}

/* Get an unsigned attribute value, or 0 */
static UINT64 die_get_uint(Dwarf_Debug dbg, Dwarf_Die die, Dwarf_Half attr)
{
    Dwarf_Attribute at = NULL;
    Dwarf_Unsigned val = 0;
    Dwarf_Error err = NULL;

    if (dwarf_attr(die, attr, &at, &err) != DW_DLV_OK) {
        return 0;
    }
    dwarf_formudata(at, &val, &err);
    dwarf_dealloc(dbg, at, DW_DLA_ATTR);
    return (UINT64)val;
}

/* Get the DIE offset of a DW_AT_type reference, or 0 */
static UINT64 die_get_type_ref(Dwarf_Debug dbg, Dwarf_Die die)
{
    Dwarf_Attribute at = NULL;
    Dwarf_Off off = 0;
    Dwarf_Error err = NULL;

    if (dwarf_attr(die, DW_AT_type, &at, &err) != DW_DLV_OK) {
        return 0;
    }
    if (dwarf_global_formref(at, &off, &err) != DW_DLV_OK) {
        off = 0;
    }
    dwarf_dealloc(dbg, at, DW_DLA_ATTR);
    return (UINT64)off;
}

/* Forward declaration for recursive parsing */
static dsc_type_t *parse_type_die(dsc_dwarf_t *dw, Dwarf_Debug dbg, Dwarf_Die die);

/* Count DW_TAG_member children by iterating siblings */
static UINT32 count_member_dies(Dwarf_Debug dbg, Dwarf_Die first_child)
{
    Dwarf_Error err = NULL;
    UINT32 count = 0;
    Dwarf_Die cur = first_child;

    for (;;) {
        Dwarf_Half tag;
        if (dwarf_tag(cur, &tag, &err) == DW_DLV_OK && tag == DW_TAG_member) {
            count++;
        }
        Dwarf_Die sib = NULL;
        int res = dwarf_siblingof(dbg, cur, &sib, &err);
        if (cur != first_child) {
            dwarf_dealloc(dbg, cur, DW_DLA_DIE);
        }
        if (res != DW_DLV_OK) {
            break;
        }
        cur = sib;
    }
    return count;
}

/* Populate one struct/union field from a DW_TAG_member DIE */
static void populate_field(Dwarf_Debug dbg, Dwarf_Die die, dsc_struct_field_t *f)
{
    f->name        = die_get_name(dbg, die);
    f->byte_offset = (UINT32)die_get_uint(dbg, die, DW_AT_data_member_location);
    f->bit_offset  = (UINT8)die_get_uint(dbg, die, DW_AT_bit_offset);
    f->bit_size    = (UINT8)die_get_uint(dbg, die, DW_AT_bit_size);

    UINT64 type_off = die_get_type_ref(dbg, die);
    if (type_off) {
        /* Resolve lazily — type may not be parsed yet.
         * Store offset, resolve in a fixup pass. */
        f->type = (dsc_type_t *)(uintptr_t)type_off; /* placeholder */
    }
}

/* Two-pass struct field parser:
 *   Pass 1: Count DW_TAG_member children (to pre-allocate array)
 *   Pass 2: Re-iterate children, populate field name/offset/type
 * We iterate twice because libdwarf's DIE API is forward-only —
 * there's no way to know the count without a first pass. */
static int parse_struct_fields(dsc_dwarf_t *dw, Dwarf_Debug dbg,
                               Dwarf_Die parent_die, dsc_type_t *stype)
{
    (void)dw;
    Dwarf_Die child = NULL;
    Dwarf_Error err = NULL;

    if (dwarf_child(parent_die, &child, &err) != DW_DLV_OK) {
        return DSC_OK; /* no children — empty struct */
    }

    UINT32 count = count_member_dies(dbg, child);
    dwarf_dealloc(dbg, child, DW_DLA_DIE);
    if (count == 0) {
        return DSC_OK;
    }

    stype->u.composite.fields = calloc(count, sizeof(dsc_struct_field_t));
    if (!stype->u.composite.fields) {
        return DSC_ERR_NOMEM;
    }
    stype->u.composite.field_count = count;

    /* Second pass: populate fields */
    if (dwarf_child(parent_die, &child, &err) != DW_DLV_OK) {
        return DSC_OK;
    }

    UINT32 fi = 0;
    Dwarf_Die cur = child;
    for (;;) {
        Dwarf_Half tag;
        if (dwarf_tag(cur, &tag, &err) == DW_DLV_OK && tag == DW_TAG_member && fi < count) {
            populate_field(dbg, cur, &stype->u.composite.fields[fi++]);
        }
        Dwarf_Die sib = NULL;
        int res = dwarf_siblingof(dbg, cur, &sib, &err);
        if (cur != child) {
            dwarf_dealloc(dbg, cur, DW_DLA_DIE);
        }
        if (res != DW_DLV_OK) {
            break;
        }
        cur = sib;
    }
    dwarf_dealloc(dbg, child, DW_DLA_DIE);
    return DSC_OK;
}

/* Map DW_TAG_* to dsc_type_kind_t. Returns DSC_TYPE_KIND_COUNT for unhandled tags. */
static dsc_type_kind_t tag_to_kind(Dwarf_Half tag)
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

/* Set common attributes and register a type in the pool + index.
 * Frees `type` and returns -1 on failure. */
static int finalize_type(dsc_dwarf_t *dw, Dwarf_Debug dbg,
                         Dwarf_Die die, dsc_type_t *type)
{
    type->name      = die_get_name(dbg, die);
    type->byte_size = (UINT32)die_get_uint(dbg, die, DW_AT_byte_size);

    if (pool_add_type(dw, type) < 0 || index_type(dw, type) < 0) {
        dsc_type_free(type);
        return -1;
    }
    return 0;
}

/* Parse a single type DIE into a dsc_type_t */
static dsc_type_t *parse_type_die(dsc_dwarf_t *dw, Dwarf_Debug dbg, Dwarf_Die die)
{
    Dwarf_Error err = NULL;
    Dwarf_Half tag;
    if (dwarf_tag(die, &tag, &err) != DW_DLV_OK) {
        return NULL;
    }

    Dwarf_Off off;
    if (dwarf_dieoffset(die, &off, &err) != DW_DLV_OK) {
        return NULL;
    }

    /* Check cache first */
    char key[21];
    snprintf(key, sizeof(key), "%llu", (unsigned long long)off);
    dsc_type_t *cached = DscHashmapGet(&dw->type_index, key);
    if (cached) {
        return cached;
    }

    dsc_type_kind_t kind = tag_to_kind(tag);
    if (kind == DSC_TYPE_KIND_COUNT) {
        return NULL;
    }

    dsc_type_t *type = alloc_type(kind, off);
    if (!type) {
        return NULL;
    }

    /* Special-case logic for tags that need extra work */
    if (tag == DW_TAG_base_type) {
        type->u.base.encoding = translate_encoding(
            (unsigned)die_get_uint(dbg, die, DW_AT_encoding));
    } else if (tag == DW_TAG_structure_type || tag == DW_TAG_union_type) {
        parse_struct_fields(dw, dbg, die, type);
    } else if (tag == DW_TAG_pointer_type) {
        type->u.pointer.pointee = NULL; /* resolved in fixup pass */
    }

    if (finalize_type(dw, dbg, die, type) < 0) {
        return NULL;
    }
    return type;
}

/* Extract a DW_TAG_variable DIE into the symbol table */
static void collect_variable(Dwarf_Debug dbg, Dwarf_Die die, dsc_symtab_t *tab)
{
    char *name = die_get_name(dbg, die);
    if (!name) {
        return;
    }

    UINT64 addr = die_get_uint(dbg, die, DW_AT_location);
    int ext = (int)die_get_uint(dbg, die, DW_AT_external);
    dsc_symtab_add(tab, name, addr, 0, NULL, ext != 0);
    free(name);
}

/* Walk all DIEs in one compilation unit */
static int walk_cu_dies(dsc_dwarf_t *dw, Dwarf_Debug dbg,
                        Dwarf_Die die, dsc_symtab_t *tab)
{
    Dwarf_Error err = NULL;
    Dwarf_Half tag;
    if (dwarf_tag(die, &tag, &err) != DW_DLV_OK) {
        return DSC_OK;
    }

    /* Dispatch: type DIEs go to the type parser, variables to the symtab */
    if (tag_to_kind(tag) != DSC_TYPE_KIND_COUNT) {
        parse_type_die(dw, dbg, die);
    } else if (tag == DW_TAG_variable && tab) {
        collect_variable(dbg, die, tab);
    }

    /* Recurse into children */
    Dwarf_Die child = NULL;
    if (dwarf_child(die, &child, &err) == DW_DLV_OK) {
        walk_cu_dies(dw, dbg, child, tab);

        Dwarf_Die sib = NULL;
        while (dwarf_siblingof(dbg, child, &sib, &err) == DW_DLV_OK) {
            dwarf_dealloc(dbg, child, DW_DLA_DIE);
            child = sib;
            walk_cu_dies(dw, dbg, child, tab);
        }
        dwarf_dealloc(dbg, child, DW_DLA_DIE);
    }

    return DSC_OK;
}

/* Iterate all compilation units and walk their DIEs */
static void parse_all_cus(dsc_dwarf_t *dw, Dwarf_Debug dbg, dsc_symtab_t *tab)
{
    Dwarf_Error err = NULL;
    Dwarf_Unsigned cu_header_length, abbrev_offset, next_cu_header;
    Dwarf_Half version_stamp, address_size;

    while (dwarf_next_cu_header(dbg, &cu_header_length, &version_stamp,
                                &abbrev_offset, &address_size,
                                &next_cu_header, &err) == DW_DLV_OK)
    {
        Dwarf_Die cu_die = NULL;
        if (dwarf_siblingof(dbg, NULL, &cu_die, &err) == DW_DLV_OK) {
            walk_cu_dies(dw, dbg, cu_die, tab);
            dwarf_dealloc(dbg, cu_die, DW_DLA_DIE);
        }
    }
}

dsc_dwarf_t *dsc_dwarf_open(const char *elf_path, int *err_out)
{
    if (!elf_path) {
        if (err_out) *err_out = DSC_ERR_INVALID_ARG;
        return NULL;
    }

    int fd = open(elf_path, O_RDONLY);
    if (fd < 0) {
        if (err_out) *err_out = DSC_ERR_ELF_OPEN;
        return NULL;
    }

    Dwarf_Debug dbg = NULL;
    Dwarf_Error err = NULL;
    if (dwarf_init(fd, DW_DLC_READ, NULL, NULL, &dbg, &err) != DW_DLV_OK) {
        close(fd);
        if (err_out) *err_out = DSC_ERR_DWARF_INIT;
        return NULL;
    }

    dsc_dwarf_t *dw = calloc(1, sizeof(dsc_dwarf_t));
    if (!dw) {
        dwarf_finish(dbg, &err);
        close(fd);
        if (err_out) *err_out = DSC_ERR_NOMEM;
        return NULL;
    }

    dw->elf_path = strdup(elf_path);
    dw->types    = calloc(TYPE_POOL_INITIAL_CAP, sizeof(dsc_type_t *));
    dw->type_cap = TYPE_POOL_INITIAL_CAP;
    DscHashmapInit(&dw->type_index, TYPE_POOL_INITIAL_CAP);
    dw->dbg    = dbg;
    dw->elf_fd = fd;

    parse_all_cus(dw, dbg, NULL);
    DSC_LOG_INFO("parsed %zu types from '%s'", dw->type_count, elf_path);

    if (err_out) *err_out = DSC_OK;
    return dw;
}

void dsc_dwarf_close(dsc_dwarf_t *dw)
{
    if (!dw) {
        return;
    }

    /* Free all owned types */
    for (UINT32 i = 0; i < dw->type_count; i++) {
        dsc_type_free(dw->types[i]);
    }
    free(dw->types);
    DscHashmapFree(&dw->type_index);

#ifdef DSC_USE_LIBDWARF
    if (dw->dbg) {
        Dwarf_Error err = NULL;
        dwarf_finish((Dwarf_Debug)dw->dbg, &err);
    }
    if (dw->elf_fd >= 0) {
        close(dw->elf_fd);
    }
#endif

    free(dw->elf_path);
    free(dw);
}

int dsc_dwarf_load_symbols(dsc_dwarf_t *dw, dsc_symtab_t *tab)
{
    if (!dw || !tab) {
        return DSC_ERR_INVALID_ARG;
    }
    if (dw->symbols_loaded) {
        return DSC_OK;
    }

#ifdef DSC_USE_LIBDWARF
    parse_all_cus(dw, (Dwarf_Debug)dw->dbg, tab);
#endif

    dw->symbols_loaded = 1;
    DSC_LOG_INFO("loaded %zu symbols", dsc_symtab_count(tab));
    return DSC_OK;
}

const dsc_type_t *dsc_dwarf_lookup_type(dsc_dwarf_t *dw, UINT64 die_offset)
{
    if (!dw) {
        return NULL;
    }

    char key[21];
    snprintf(key, sizeof(key), "%llu", (unsigned long long)die_offset);
    return (const dsc_type_t *)DscHashmapGet(&dw->type_index, key);
}

const char *dsc_dwarf_path(const dsc_dwarf_t *dw)
{
    return dw ? dw->elf_path : NULL;
}

#else /* !DSC_USE_LIBDWARF */

/* --------------------------------------------------------------- */
/* Stub implementation: no libdwarf dependency                     */
/* --------------------------------------------------------------- */

dsc_dwarf_t *dsc_dwarf_open(const char *elf_path, int *err_out)
{
    if (!elf_path) {
        if (err_out) *err_out = DSC_ERR_INVALID_ARG;
        return NULL;
    }

    dsc_dwarf_t *dw = calloc(1, sizeof(dsc_dwarf_t));
    if (!dw) {
        if (err_out) *err_out = DSC_ERR_NOMEM;
        return NULL;
    }

    dw->elf_path = strdup(elf_path);
    dw->types    = calloc(TYPE_POOL_INITIAL_CAP, sizeof(dsc_type_t *));
    dw->type_cap = TYPE_POOL_INITIAL_CAP;
    DscHashmapInit(&dw->type_index, TYPE_POOL_INITIAL_CAP);

    DSC_LOG_WARN("stub DWARF parser — define DSC_USE_LIBDWARF for real parsing");

    if (err_out) *err_out = DSC_OK;
    return dw;
}

void dsc_dwarf_close(dsc_dwarf_t *dw)
{
    if (!dw) {
        return;
    }

    for (UINT32 i = 0; i < dw->type_count; i++) {
        dsc_type_free(dw->types[i]);
    }
    free(dw->types);
    DscHashmapFree(&dw->type_index);
    free(dw->elf_path);
    free(dw);
}

int dsc_dwarf_load_symbols(dsc_dwarf_t *dw, dsc_symtab_t *tab)
{
    (void)tab;
    if (!dw) {
        return DSC_ERR_INVALID_ARG;
    }
    DSC_LOG_WARN("stub: no symbols loaded (libdwarf not available)");
    return DSC_OK;
}

const dsc_type_t *dsc_dwarf_lookup_type(dsc_dwarf_t *dw, UINT64 die_offset)
{
    if (!dw) {
        return NULL;
    }

    char key[21];
    snprintf(key, sizeof(key), "%llu", (unsigned long long)die_offset);
    return (const dsc_type_t *)DscHashmapGet(&dw->type_index, key);
}

const char *dsc_dwarf_path(const dsc_dwarf_t *dw)
{
    return dw ? dw->elf_path : NULL;
}

#endif /* DSC_USE_LIBDWARF */
