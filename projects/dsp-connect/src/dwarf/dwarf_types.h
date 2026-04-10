/* PURPOSE: Tagged-union type representation for DWARF debug info types
 * PATTERN: X-macro for enumerations, tagged union for type variants
 * FOR: Weak AI to reference when building a type system from DWARF DIEs */

#ifndef DSC_DWARF_TYPES_H
#define DSC_DWARF_TYPES_H

#include "../util/types.h"

/* ------------------------------------------------------------------ */
/* X-macro: base encoding kinds (maps to DW_ATE_*)                    */
/* ------------------------------------------------------------------ */
#define DSC_BASE_ENCODING_TABLE(X) \
    X(DSC_ENC_SIGNED,    "signed")   \
    X(DSC_ENC_UNSIGNED,  "unsigned") \
    X(DSC_ENC_FLOAT,     "float")    \
    X(DSC_ENC_BOOL,      "bool")     \
    X(DSC_ENC_CHAR,      "char")

#define X_ENUM(name, str) name,
typedef enum {
    DSC_BASE_ENCODING_TABLE(X_ENUM)
    DSC_ENC_COUNT
} dsc_base_encoding_t;
#undef X_ENUM

/* ------------------------------------------------------------------ */
/* X-macro: type kind discriminator                                   */
/* ------------------------------------------------------------------ */
#define DSC_TYPE_KIND_TABLE(X) \
    X(DSC_TYPE_BASE,     "base")     \
    X(DSC_TYPE_STRUCT,   "struct")   \
    X(DSC_TYPE_UNION,    "union")    \
    X(DSC_TYPE_ENUM,     "enum")     \
    X(DSC_TYPE_ARRAY,    "array")    \
    X(DSC_TYPE_POINTER,  "pointer")  \
    X(DSC_TYPE_TYPEDEF,  "typedef")  \
    X(DSC_TYPE_CONST,    "const")    \
    X(DSC_TYPE_VOLATILE, "volatile") \
    X(DSC_TYPE_VOID,     "void")     \
    X(DSC_TYPE_FUNC,     "function") \
    X(DSC_TYPE_BITFIELD, "bitfield")

#define X_ENUM(name, str) name,
typedef enum {
    DSC_TYPE_KIND_TABLE(X_ENUM)
    DSC_TYPE_KIND_COUNT
} dsc_type_kind_t;
#undef X_ENUM

/* ------------------------------------------------------------------ */
/* Forward declaration                                                */
/* ------------------------------------------------------------------ */
typedef struct dsc_type dsc_type_t;

/* ------------------------------------------------------------------ */
/* Struct / union field                                                */
/* ------------------------------------------------------------------ */
typedef struct {
    char       *name;         /* field name (owned, heap-allocated) */
    UINT32      byte_offset;  /* offset within parent struct/union  */
    UINT8     bit_offset;   /* additional bit offset (0 for non-bitfield) */
    UINT8     bit_size;     /* bit width (0 for non-bitfield)     */
    dsc_type_t *type;         /* borrowed — owned by dsc_dwarf_t    */
} dsc_struct_field_t;

/* ------------------------------------------------------------------ */
/* Enum value                                                         */
/* ------------------------------------------------------------------ */
typedef struct {
    char    *name;   /* enumerator name (owned) */
    INT64  value;
} dsc_enum_value_t;

/* ------------------------------------------------------------------ */
/* Array dimension                                                    */
/* ------------------------------------------------------------------ */
typedef struct {
    INT64 lower_bound;  /* usually 0 for C */
    UINT32  count;        /* element count; 0 = flexible array */
} dsc_array_dim_t;

/* ------------------------------------------------------------------ */
/* Tagged union: one struct, many shapes                              */
/* ------------------------------------------------------------------ */
struct dsc_type {
    dsc_type_kind_t kind;
    char           *name;       /* type name, may be NULL (e.g. anon struct) */
    UINT32          byte_size;  /* sizeof, 0 if unknown / void              */
    UINT64        die_offset; /* DWARF DIE offset — used as unique ID     */

    /* Variant data — ownership rules:
     *   composite.fields[]  — OWNED: freed by dsc_type_free()
     *   enumeration.values[] — OWNED: freed by dsc_type_free()
     *   array.dims[]        — OWNED: freed by dsc_type_free()
     *   pointer.pointee     — BORROWED: points into the type pool, do NOT free
     *   typedef_ref.target  — BORROWED: points into the type pool, do NOT free
     *   const_ref/volatile_ref — BORROWED: same as typedef */
    union {
        /* DSC_TYPE_BASE */
        struct {
            dsc_base_encoding_t encoding;
        } base;

        /* DSC_TYPE_STRUCT, DSC_TYPE_UNION */
        struct {
            dsc_struct_field_t *fields;      /* owned array */
            UINT32              field_count;
        } composite;

        /* DSC_TYPE_ENUM */
        struct {
            dsc_enum_value_t *values;        /* owned array */
            UINT32            value_count;
            dsc_type_t       *underlying;    /* borrowed — the integer base type */
        } enumeration;

        /* DSC_TYPE_ARRAY */
        struct {
            dsc_type_t    *element_type;     /* borrowed */
            dsc_array_dim_t *dims;           /* owned array */
            UINT32           dim_count;
        } array;

        /* DSC_TYPE_POINTER */
        struct {
            dsc_type_t *pointee;             /* borrowed, NULL for void* */
        } pointer;

        /* DSC_TYPE_TYPEDEF, DSC_TYPE_CONST, DSC_TYPE_VOLATILE */
        struct {
            dsc_type_t *target;              /* borrowed — what this qualifies */
        } modifier;

        /* DSC_TYPE_FUNC */
        struct {
            dsc_type_t  *return_type;        /* borrowed */
            dsc_type_t **param_types;        /* owned array of borrowed ptrs */
            UINT32       param_count;
        } func;

        /* DSC_TYPE_BITFIELD */
        struct {
            dsc_type_t *base_type;           /* borrowed — underlying integer */
            UINT8     bit_offset;
            UINT8     bit_size;
        } bitfield;

        /* DSC_TYPE_VOID — no extra data */
    } u;
};

/* ------------------------------------------------------------------ */
/* API                                                                */
/* ------------------------------------------------------------------ */

/* Returns human-readable name for a type kind (from X-macro) */
const char *dsc_type_kind_name(dsc_type_kind_t kind);

/* Returns human-readable name for a base encoding (from X-macro) */
const char *dsc_base_encoding_name(dsc_base_encoding_t enc);

/* Byte size of the type (reads byte_size field, follows typedefs) */
UINT32 dsc_type_size(const dsc_type_t *type);

/* Unwrap typedef / const / volatile chain to get the real type */
const dsc_type_t *dsc_type_resolve_typedef(const dsc_type_t *type);

/* Deep free: frees owned arrays, field names, etc. Does NOT free borrowed types. */
void dsc_type_free(dsc_type_t *type);

#endif /* DSC_DWARF_TYPES_H */
