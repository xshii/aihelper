/* PURPOSE: Symbol path resolver — parses "g_config.items[2].name" and walks
 *          the type tree to compute the final address, size, and type.
 * PATTERN: Recursive-descent parser with iterative segment consumption.
 *          Each segment is either ".field" or "[index]". The parser accumulates
 *          byte offsets while descending through the type tree.
 * FOR: 弱 AI 参考如何实现路径表达式解析（如 "a.b[3].c"） */

#include "resolve.h"

#include <string.h>
#include <stdlib.h>
#include <ctype.h>

#include "../core/dsc_errors.h"
#include "../util/log.h"

/* ------------------------------------------------------------------ */
/* Internal: path segment types                                       */
/* ------------------------------------------------------------------ */
typedef enum {
    SEG_FIELD,   /* ".field_name" or the root identifier              */
    SEG_INDEX    /* "[123]"                                           */
} seg_kind_t;

typedef struct {
    seg_kind_t kind;
    union {
        char   name[256]; /* SEG_FIELD: field / symbol name           */
        size_t index;     /* SEG_INDEX: array index                   */
    } u;
} segment_t;

/* ------------------------------------------------------------------ */
/* Internal: parse an array index segment "[123]" from p.             */
/* On success, fills seg and advances *cursor past ']'. Returns 1.    */
/* On error, returns a negative error code.                           */
/* ------------------------------------------------------------------ */
static int parse_array_index(const char *p, const char **cursor,
                             segment_t *seg)
{
    p++; /* skip '[' */
    if (!isdigit((unsigned char)*p)) {
        DSC_LOG_ERROR("resolve: expected digit after '[' in path");
        return DSC_ERR_RESOLVE_PATH;
    }
    char *end = NULL;
    unsigned long idx = strtoul(p, &end, 10);
    if (end == NULL || *end != ']') {
        DSC_LOG_ERROR("resolve: expected ']' after array index");
        return DSC_ERR_RESOLVE_PATH;
    }
    seg->kind = SEG_INDEX;
    seg->u.index = (size_t)idx;
    *cursor = end + 1; /* skip ']' */
    return 1;
}

/* ------------------------------------------------------------------ */
/* Internal: parse the next segment from *cursor, advance cursor.     */
/* Returns 1 if a segment was parsed, 0 if end-of-string, negative   */
/* on error.                                                          */
/* ------------------------------------------------------------------ */
static int parse_next_segment(const char **cursor, segment_t *seg)
{
    const char *p = *cursor;

    /* End of path */
    if (*p == '\0') {
        return 0;
    }

    /* Array index: "[123]" */
    if (*p == '[') {
        return parse_array_index(p, cursor, seg);
    }

    /* Dot separator: skip it, then parse the field name */
    if (*p == '.') {
        p++; /* skip '.' */
    }

    /* Field name: identifier chars [a-zA-Z0-9_] */
    if (!isalpha((unsigned char)*p) && *p != '_') {
        DSC_LOG_ERROR("resolve: expected identifier at '%.20s'", p);
        return DSC_ERR_RESOLVE_PATH;
    }

    const char *start = p;
    while (isalnum((unsigned char)*p) || *p == '_') {
        p++;
    }

    size_t len = (size_t)(p - start);
    if (len >= sizeof(seg->u.name)) {
        DSC_LOG_ERROR("resolve: field name too long (%zu chars)", len);
        return DSC_ERR_RESOLVE_PATH;
    }
    seg->kind = SEG_FIELD;
    memcpy(seg->u.name, start, len);
    seg->u.name[len] = '\0';

    *cursor = p;
    return 1;
}

/* ------------------------------------------------------------------ */
/* Internal: unwrap typedef/const/volatile modifiers to get real type  */
/* ------------------------------------------------------------------ */
static const dsc_type_t *unwrap_modifiers(const dsc_type_t *type)
{
    while (type != NULL) {
        if (type->kind == DSC_TYPE_TYPEDEF ||
            type->kind == DSC_TYPE_CONST   ||
            type->kind == DSC_TYPE_VOLATILE) {
            type = type->u.modifier.target;
        } else {
            break;
        }
    }
    return type;
}

/* ------------------------------------------------------------------ */
/* Internal: find a field by name in a struct/union type.             */
/* Returns pointer to field or NULL.                                  */
/* ------------------------------------------------------------------ */
static const dsc_struct_field_t *find_field(const dsc_type_t *composite,
                                            const char *name)
{
    for (size_t i = 0; i < composite->u.composite.field_count; i++) {
        const dsc_struct_field_t *f = &composite->u.composite.fields[i];
        if (f->name != NULL && strcmp(f->name, name) == 0) {
            return f;
        }
    }
    return NULL;
}

/* ------------------------------------------------------------------ */
/* Public API                                                         */
/* ------------------------------------------------------------------ */
int dsc_resolve(const dsc_symtab_t *symtab, const dsc_arch_t *arch,
                const char *path, dsc_resolved_t *out)
{
    (void)arch;
    if (symtab == NULL || path == NULL || out == NULL) {
        return DSC_ERR_INVALID_ARG;
    }
    if (*path == '\0') {
        return DSC_ERR_INVALID_ARG;
    }

    const char *cursor = path;
    segment_t seg;

    /* -------------------------------------------------------------- */
    /* Step 1: parse the root symbol name                             */
    /* -------------------------------------------------------------- */
    int rc = parse_next_segment(&cursor, &seg);
    if (rc <= 0) {
        DSC_LOG_ERROR("resolve: empty path");
        return DSC_ERR_RESOLVE_PATH;
    }
    if (seg.kind != SEG_FIELD) {
        DSC_LOG_ERROR("resolve: path must start with an identifier");
        return DSC_ERR_RESOLVE_PATH;
    }

    const dsc_symbol_t *sym = dsc_symtab_lookup(symtab, seg.u.name);
    if (sym == NULL) {
        DSC_LOG_ERROR("resolve: symbol '%s' not found", seg.u.name);
        return DSC_ERR_NOT_FOUND;
    }

    uint64_t addr = sym->address;
    const dsc_type_t *type = unwrap_modifiers(sym->type);
    size_t size = (type != NULL) ? type->byte_size : sym->size;

    /* -------------------------------------------------------------- */
    /* Step 2: consume remaining segments, accumulating offset        */
    /* -------------------------------------------------------------- */
    while ((rc = parse_next_segment(&cursor, &seg)) > 0) {

        if (type == NULL) {
            DSC_LOG_ERROR("resolve: cannot descend into untyped symbol");
            return DSC_ERR_RESOLVE_PATH;
        }

        if (seg.kind == SEG_FIELD) {
            /* ---- Struct/union field access ---- */
            const dsc_type_t *real = unwrap_modifiers(type);
            if (real == NULL ||
                (real->kind != DSC_TYPE_STRUCT && real->kind != DSC_TYPE_UNION)) {
                DSC_LOG_ERROR("resolve: '%.64s' is not a struct/union, "
                              "cannot access field '%s'",
                              type->name ? type->name : "(anon)",
                              seg.u.name);
                return DSC_ERR_RESOLVE_PATH;
            }

            const dsc_struct_field_t *field = find_field(real, seg.u.name);
            if (field == NULL) {
                DSC_LOG_ERROR("resolve: field '%s' not found in '%s'",
                              seg.u.name,
                              real->name ? real->name : "(anon)");
                return DSC_ERR_NOT_FOUND;
            }

            addr += field->byte_offset;
            type = unwrap_modifiers(field->type);
            size = (type != NULL) ? type->byte_size : 0;

        } else {
            /* ---- Array index access ---- */
            const dsc_type_t *real = unwrap_modifiers(type);
            if (real == NULL || real->kind != DSC_TYPE_ARRAY) {
                DSC_LOG_ERROR("resolve: cannot index non-array type");
                return DSC_ERR_RESOLVE_PATH;
            }

            /* Bounds check (only if element count is known and non-zero) */
            if (real->u.array.dim_count > 0 &&
                real->u.array.dims[0].count > 0 &&
                seg.u.index >= real->u.array.dims[0].count) {
                DSC_LOG_ERROR("resolve: index %zu out of bounds (count=%zu)",
                              seg.u.index, real->u.array.dims[0].count);
                return DSC_ERR_RESOLVE_INDEX;
            }

            const dsc_type_t *elem = unwrap_modifiers(real->u.array.element_type);
            if (elem == NULL) {
                DSC_LOG_ERROR("resolve: array has no element type");
                return DSC_ERR_TYPE_INCOMPLETE;
            }

            addr += seg.u.index * elem->byte_size;
            type = elem;
            size = elem->byte_size;
        }
    }

    /* rc < 0 means parse error */
    if (rc < 0) {
        return rc;
    }

    /* -------------------------------------------------------------- */
    /* Step 3: fill output                                            */
    /* -------------------------------------------------------------- */
    out->addr = addr;
    out->size = size;
    out->type = (dsc_type_t *)type; /* borrowed pointer, safe cast */

    DSC_LOG_DEBUG("resolve: '%s' → addr=0x%llx size=%zu",
                  path, (unsigned long long)addr, size);
    return DSC_OK;
}
