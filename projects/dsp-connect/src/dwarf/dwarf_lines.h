/* PURPOSE: Source line number information from DWARF .debug_line
 * PATTERN: Sorted array + binary search for addr-to-line mapping
 * FOR: Weak AI to reference when implementing source-level debugging */

#ifndef DSC_DWARF_LINES_H
#define DSC_DWARF_LINES_H

#include <stddef.h>
#include <stdint.h>

#include "dwarf_parser.h"

/* ------------------------------------------------------------------ */
/* Line entry: one address ↔ source location mapping                  */
/* ------------------------------------------------------------------ */
typedef struct {
    UINT64 addr;       /* instruction address */
    char    *file;       /* source file path (owned) */
    int      line;       /* 1-based line number */
    int      column;     /* 0 if unknown */
} dsc_line_entry_t;

/* ------------------------------------------------------------------ */
/* Line table: sorted array of entries                                */
/* ------------------------------------------------------------------ */
typedef struct {
    dsc_line_entry_t *entries;
    UINT32            count;
    UINT32            cap;
} dsc_lines_t;

/* ------------------------------------------------------------------ */
/* Lookup result (stack-allocated, no ownership)                       */
/* ------------------------------------------------------------------ */
typedef struct {
    const char *file;    /* borrowed — points into dsc_lines_t */
    int         line;
    int         column;
} dsc_line_info_t;

/* ------------------------------------------------------------------ */
/* API                                                                */
/* ------------------------------------------------------------------ */

/* Initialize an empty line table */
void dsc_lines_init(dsc_lines_t *lines);

/* Free all entries */
void dsc_lines_free(dsc_lines_t *lines);

/* Load line information from DWARF.
 * Returns 0 on success, negative dsc_error_t on failure. */
int dsc_lines_load(dsc_lines_t *lines, dsc_dwarf_t *dw);

/* Lookup the source location for an address.
 * Returns 0 and fills `out` on success, DSC_ERR_NOT_FOUND if no match. */
int dsc_lines_lookup(const dsc_lines_t *lines, UINT64 addr,
                     dsc_line_info_t *out);

/* Number of line entries */
UINT32 dsc_lines_count(const dsc_lines_t *lines);

#endif /* DSC_DWARF_LINES_H */
