/* PURPOSE: Utility functions for the tagged-union type system
 * PATTERN: X-macro expansion for string tables, switch-on-kind for dispatch
 * FOR: Weak AI to reference when implementing type introspection helpers */

#include <stdlib.h>
#include <string.h>

#include "dwarf_types.h"

/* ------------------------------------------------------------------ */
/* X-macro → string tables                                            */
/* ------------------------------------------------------------------ */

#define X_STR(name, str) [name] = str,

static const char *type_kind_names[DSC_TYPE_KIND_COUNT] = {
    DSC_TYPE_KIND_TABLE(X_STR)
};

static const char *base_encoding_names[DSC_ENC_COUNT] = {
    DSC_BASE_ENCODING_TABLE(X_STR)
};

#undef X_STR

const char *dsc_type_kind_name(dsc_type_kind_t kind)
{
    if (kind >= 0 && kind < DSC_TYPE_KIND_COUNT) {
        return type_kind_names[kind];
    }
    return "unknown";
}

const char *dsc_base_encoding_name(dsc_base_encoding_t enc)
{
    if (enc >= 0 && enc < DSC_ENC_COUNT) {
        return base_encoding_names[enc];
    }
    return "unknown";
}

/* ------------------------------------------------------------------ */
/* dsc_type_resolve_typedef — peel off qualifier wrappers              */
/* ------------------------------------------------------------------ */

const dsc_type_t *dsc_type_resolve_typedef(const dsc_type_t *type)
{
    /* Walk through typedef / const / volatile chain until we hit a real type.
     * Safety limit prevents infinite loops on malformed DWARF. */
    int limit = 64;
    while (type && limit-- > 0) {
        switch (type->kind) {
        case DSC_TYPE_TYPEDEF:
        case DSC_TYPE_CONST:
        case DSC_TYPE_VOLATILE:
            type = type->u.modifier.target;
            break;
        default:
            return type;
        }
    }
    return type;
}

/* ------------------------------------------------------------------ */
/* dsc_type_size — byte size, resolving through typedefs               */
/* ------------------------------------------------------------------ */

UINT32 dsc_type_size(const dsc_type_t *type)
{
    const dsc_type_t *resolved = dsc_type_resolve_typedef(type);
    if (!resolved) {
        return 0;
    }
    return resolved->byte_size;
}

/* ------------------------------------------------------------------ */
/* dsc_type_free — release owned resources                             */
/* ------------------------------------------------------------------ */

/* Helper: free a single field's owned data */
static void free_field(dsc_struct_field_t *f)
{
    free(f->name);
    /* f->type is borrowed, do NOT free */
}

void dsc_type_free(dsc_type_t *type)
{
    if (!type) {
        return;
    }

    /* Free the type name (all kinds may have one) */
    free(type->name);

    /* Free kind-specific owned data */
    switch (type->kind) {
    case DSC_TYPE_STRUCT:
    case DSC_TYPE_UNION:
        for (UINT32 i = 0; i < type->u.composite.field_count; i++) {
            free_field(&type->u.composite.fields[i]);
        }
        free(type->u.composite.fields);
        break;

    case DSC_TYPE_ENUM:
        for (UINT32 i = 0; i < type->u.enumeration.value_count; i++) {
            free(type->u.enumeration.values[i].name);
        }
        free(type->u.enumeration.values);
        break;

    case DSC_TYPE_ARRAY:
        free(type->u.array.dims);
        break;

    case DSC_TYPE_FUNC:
        free(type->u.func.param_types);
        break;

    case DSC_TYPE_BASE:
    case DSC_TYPE_POINTER:
    case DSC_TYPE_TYPEDEF:
    case DSC_TYPE_CONST:
    case DSC_TYPE_VOLATILE:
    case DSC_TYPE_VOID:
    case DSC_TYPE_BITFIELD:
        /* No owned heap data beyond type->name */
        break;

    case DSC_TYPE_KIND_COUNT:
        /* Sentinel — should never appear in a real type */
        break;
    }

    free(type);
}
