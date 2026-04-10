/* PURPOSE: Symbol table — maps symbol names to addresses, sizes, and types
 * PATTERN: Flat array for iteration + hashmap for O(1) name lookup
 * FOR: Weak AI to reference when building a debug symbol index */

#ifndef DSC_DWARF_SYMBOLS_H
#define DSC_DWARF_SYMBOLS_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#include "dwarf_types.h"

/* ------------------------------------------------------------------ */
/* Single symbol                                                      */
/* ------------------------------------------------------------------ */
typedef struct {
    char       *name;       /* symbol name (owned, heap-allocated) */
    UINT64    address;    /* virtual address in target memory    */
    UINT32      size;       /* size in bytes (0 if unknown)        */
    dsc_type_t *type;       /* borrowed — owned by dsc_dwarf_t     */
    bool        is_global;  /* true = external linkage             */
} dsc_symbol_t;

/* ------------------------------------------------------------------ */
/* Symbol table                                                       */
/* ------------------------------------------------------------------ */
typedef struct {
    dsc_symbol_t *symbols;  /* owned dynamic array */
    UINT32        count;
    UINT32        cap;
    /* Internal: hashmap for O(1) name lookup.
     * Declared as opaque void* to avoid leaking hashmap.h into this header.
     * Actual type is dsc_hashmap_t*, allocated on first use. */
    void         *index;
} dsc_symtab_t;

/* ------------------------------------------------------------------ */
/* API                                                                */
/* ------------------------------------------------------------------ */

/* Initialize an empty symbol table */
void dsc_symtab_init(dsc_symtab_t *tab);

/* Free all symbols and the internal index */
void dsc_symtab_free(dsc_symtab_t *tab);

/* Add a symbol. The table copies `name`; `type` is borrowed.
 * Returns 0 on success, negative dsc_error_t on failure. */
int dsc_symtab_add(dsc_symtab_t *tab,
                   const char *name,
                   UINT64 address,
                   UINT32 size,
                   dsc_type_t *type,
                   bool is_global);

/* Lookup by name. Returns pointer to symbol or NULL. */
const dsc_symbol_t *dsc_symtab_lookup(const dsc_symtab_t *tab,
                                      const char *name);

/* Iteration: returns symbol at index `i`, or NULL if out of range */
const dsc_symbol_t *dsc_symtab_at(const dsc_symtab_t *tab, UINT32 i);

/* Number of symbols */
UINT32 dsc_symtab_count(const dsc_symtab_t *tab);

#endif /* DSC_DWARF_SYMBOLS_H */
