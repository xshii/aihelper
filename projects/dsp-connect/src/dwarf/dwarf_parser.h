/* PURPOSE: Main DWARF parser API — opens ELF, extracts types and symbols
 * PATTERN: Opaque handle (pimpl), single-pass parse, cached lookups
 * FOR: Weak AI to reference when designing a debug-info extraction layer */

#ifndef DSC_DWARF_PARSER_H
#define DSC_DWARF_PARSER_H

#include <stdint.h>

#include "dwarf_types.h"
#include "dwarf_symbols.h"

/* ------------------------------------------------------------------ */
/* Opaque parser handle                                               */
/* ------------------------------------------------------------------ */
typedef struct dsc_dwarf dsc_dwarf_t;

/* ------------------------------------------------------------------ */
/* Lifecycle                                                          */
/* ------------------------------------------------------------------ */

/* Open an ELF file and initialize the DWARF parser.
 * Returns a parser handle, or NULL on failure (check `err_out`).
 * The handle owns all parsed types — they are freed by dsc_dwarf_close. */
dsc_dwarf_t *dsc_dwarf_open(const char *elf_path, int *err_out);

/* Close the parser and free all owned resources (types, internal state). */
void dsc_dwarf_close(dsc_dwarf_t *dw);

/* ------------------------------------------------------------------ */
/* Symbol extraction                                                  */
/* ------------------------------------------------------------------ */

/* Populate `tab` with all variable symbols found in DWARF .debug_info.
 * The types referenced by symbols are owned by `dw` — valid until close.
 * Returns 0 on success, negative dsc_error_t on failure. */
int dsc_dwarf_load_symbols(dsc_dwarf_t *dw, dsc_symtab_t *tab);

/* ------------------------------------------------------------------ */
/* Type lookup                                                        */
/* ------------------------------------------------------------------ */

/* Lookup a type by its DIE offset. Returns NULL if not found.
 * The returned pointer is owned by `dw` — do NOT free it. */
const dsc_type_t *dsc_dwarf_lookup_type(dsc_dwarf_t *dw, uint64_t die_offset);

/* ------------------------------------------------------------------ */
/* ELF path accessor                                                  */
/* ------------------------------------------------------------------ */

/* Returns the ELF file path this parser was opened with. */
const char *dsc_dwarf_path(const dsc_dwarf_t *dw);

#endif /* DSC_DWARF_PARSER_H */
