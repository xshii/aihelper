/* PURPOSE: Symbol table implementation — dynamic array + hashmap index
 * PATTERN: Grow-by-doubling array, lazy hashmap construction
 * FOR: Weak AI to reference when building indexed collections in C */

#include <stdlib.h>
#include <string.h>

#include "dwarf_symbols.h"
#include "../core/dsc_errors.h"
#include "../util/dsc_common.h"
#include "../util/hashmap.h"

/* Initial capacity for the symbol array */
#define INITIAL_CAP 64

/* ------------------------------------------------------------------ */
/* Init / Free                                                        */
/* ------------------------------------------------------------------ */

void dsc_symtab_init(dsc_symtab_t *tab)
{
    tab->symbols = NULL;
    tab->count   = 0;
    tab->cap     = 0;
    tab->index   = NULL;
}

void dsc_symtab_free(dsc_symtab_t *tab)
{
    if (!tab) {
        return;
    }

    /* Free each symbol's owned name */
    for (size_t i = 0; i < tab->count; i++) {
        free(tab->symbols[i].name);
        /* type is borrowed, do NOT free */
    }
    free(tab->symbols);

    /* Free the hashmap index */
    if (tab->index) {
        dsc_hashmap_t *map = (dsc_hashmap_t *)tab->index;
        dsc_hashmap_free(map);
        free(map);
    }

    tab->symbols = NULL;
    tab->count   = 0;
    tab->cap     = 0;
    tab->index   = NULL;
}

/* ------------------------------------------------------------------ */
/* Internal: ensure capacity for one more symbol                      */
/* ------------------------------------------------------------------ */
static int ensure_capacity(dsc_symtab_t *tab)
{
    if (tab->count < tab->cap) {
        return DSC_OK;
    }

    size_t new_cap = (tab->cap == 0) ? INITIAL_CAP : tab->cap * 2;
    dsc_symbol_t *new_buf = realloc(tab->symbols, new_cap * sizeof(dsc_symbol_t));
    if (!new_buf) {
        return DSC_ERR_NOMEM;
    }
    tab->symbols = new_buf;
    tab->cap     = new_cap;
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Internal: lazily create and populate the hashmap index              */
/* ------------------------------------------------------------------ */
static int ensure_index(dsc_symtab_t *tab)
{
    if (tab->index) {
        return DSC_OK;
    }

    dsc_hashmap_t *map = malloc(sizeof(dsc_hashmap_t));
    if (!map) {
        return DSC_ERR_NOMEM;
    }
    dsc_hashmap_init(map, tab->cap > 0 ? tab->cap : INITIAL_CAP);

    /* Index all existing symbols */
    for (size_t i = 0; i < tab->count; i++) {
        DSC_TRY(dsc_hashmap_put(map, tab->symbols[i].name, &tab->symbols[i]));
    }

    tab->index = map;
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Add                                                                */
/* ------------------------------------------------------------------ */

int dsc_symtab_add(dsc_symtab_t *tab,
                   const char *name,
                   uint64_t address,
                   size_t size,
                   dsc_type_t *type,
                   bool is_global)
{
    if (!tab || !name) {
        return DSC_ERR_INVALID_ARG;
    }

    DSC_TRY(ensure_capacity(tab));

    char *name_copy = strdup(name);
    if (!name_copy) {
        return DSC_ERR_NOMEM;
    }

    dsc_symbol_t *sym = &tab->symbols[tab->count];
    sym->name      = name_copy;
    sym->address   = address;
    sym->size      = size;
    sym->type      = type;
    sym->is_global = is_global;
    tab->count++;

    /* Update hashmap index if it exists */
    if (tab->index) {
        dsc_hashmap_t *map = (dsc_hashmap_t *)tab->index;
        int rc = dsc_hashmap_put(map, name_copy, sym);
        if (rc < 0) {
            /* Index failed — symbol is still in the array, just not indexed.
             * The next lookup will rebuild the index. */
            dsc_hashmap_free(map);
            free(map);
            tab->index = NULL;
        }
    }

    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Lookup                                                             */
/* ------------------------------------------------------------------ */

const dsc_symbol_t *dsc_symtab_lookup(const dsc_symtab_t *tab,
                                      const char *name)
{
    if (!tab || !name) {
        return NULL;
    }

    /* Build index lazily on first lookup (cast away const for internal state) */
    dsc_symtab_t *mut_tab = (dsc_symtab_t *)tab;
    if (ensure_index(mut_tab) < 0) {
        /* Fallback: linear scan if index allocation fails */
        for (size_t i = 0; i < tab->count; i++) {
            if (strcmp(tab->symbols[i].name, name) == 0) {
                return &tab->symbols[i];
            }
        }
        return NULL;
    }

    dsc_hashmap_t *map = (dsc_hashmap_t *)tab->index;
    return (const dsc_symbol_t *)dsc_hashmap_get(map, name);
}

/* ------------------------------------------------------------------ */
/* Iteration                                                          */
/* ------------------------------------------------------------------ */

const dsc_symbol_t *dsc_symtab_at(const dsc_symtab_t *tab, size_t i)
{
    if (!tab || i >= tab->count) {
        return NULL;
    }
    return &tab->symbols[i];
}

size_t dsc_symtab_count(const dsc_symtab_t *tab)
{
    return tab ? tab->count : 0;
}
