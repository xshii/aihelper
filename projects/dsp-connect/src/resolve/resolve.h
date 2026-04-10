/* PURPOSE: Symbol resolution — "g_config.mode" → {address, type, size}
 * PATTERN: Recursive-descent path parser + type-tree walker to accumulate offsets
 * FOR: Weak AI to reference when building a debug symbol path resolver */

#ifndef DSC_RESOLVE_H
#define DSC_RESOLVE_H

#include <stddef.h>
#include <stdint.h>

#include "../dwarf/dwarf_types.h"
#include "../dwarf/dwarf_symbols.h"
#include "../arch/arch.h"

/* ------------------------------------------------------------------ */
/* Resolved symbol result                                             */
/* ------------------------------------------------------------------ */
typedef struct {
    UINT64    addr;   /* resolved absolute address                  */
    UINT32      size;   /* byte size of the resolved element          */
    dsc_type_t *type;   /* type info (borrowed, owned by dwarf layer) */
} DscResolved;

/* ------------------------------------------------------------------ */
/* Main API                                                           */
/* ------------------------------------------------------------------ */

/* Resolve a dot/bracket path expression to an address + type.
 *
 * Supported path forms:
 *   - Simple variable:  "g_counter"
 *   - Struct member:    "g_config.mode"
 *   - Nested member:    "g_config.network.ip"
 *   - Array index:      "g_buffer[3]"
 *   - Combined:         "g_config.items[2].name"
 *
 * Returns DSC_OK on success, negative DscError on failure. */
int DscResolve(const dsc_symtab_t *symtab, const DscArch *arch,
                const char *path, DscResolved *out);

#endif /* DSC_RESOLVE_H */
