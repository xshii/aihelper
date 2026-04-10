/* PURPOSE: Main API for type-aware display — turns raw bytes + DWARF type info
 *          into human-readable formatted output
 * PATTERN: Dispatcher — switch on type->kind, delegate to sub-formatters
 * FOR: Weak AI to reference when building a data-display / pretty-print layer */

#ifndef DSC_FORMAT_H
#define DSC_FORMAT_H

#include <stddef.h>
#include "../dwarf/dwarf_types.h"
#include "../util/strbuf.h"

/* ------------------------------------------------------------------ */
/* Format options — Layer 1 progressive disclosure                     */
/* Users who just want defaults call DscFormatOptsDefault().        */
/* ------------------------------------------------------------------ */
typedef struct DscFormatOpts {
    int  max_depth;        /* max struct nesting depth (0 = unlimited)        */
    int  array_max_elems;  /* max array elements to show (0 = all)            */
    int  hex_integers;     /* 1 = show integers as hex, 0 = decimal           */
    int  show_offsets;     /* 1 = show byte offsets for struct fields          */
    int  show_type_names;  /* 1 = prefix values with type name                */
    int  indent_width;     /* spaces per indent level (default 2)             */
} DscFormatOpts;

/* Return a default options struct (Layer 0 — zero config) */
DscFormatOpts DscFormatOptsDefault(void);

/* ------------------------------------------------------------------ */
/* Main entry point                                                    */
/* Dispatches to sub-formatters by type->kind.                         */
/*                                                                     */
/* data     — pointer to raw bytes to interpret                        */
/* data_len — size of the data buffer (bounds-checked)                 */
/* type     — DWARF type describing the data layout                    */
/* opts     — format options (pass NULL for defaults)                  */
/* out      — string buffer to append formatted output to              */
/*                                                                     */
/* Returns DSC_OK on success, negative error code on failure.          */
/* ------------------------------------------------------------------ */
int DscFormat(const void *data, UINT32 data_len,
               const dsc_type_t *type, const DscFormatOpts *opts,
               DscStrbuf *out);

/* Convenience: format and return a newly allocated string.
 * Caller must free() the returned pointer. Returns NULL on error. */
char *DscFormatStr(const void *data, UINT32 data_len,
                     const dsc_type_t *type, const DscFormatOpts *opts);

/* ------------------------------------------------------------------ */
/* Internal: format with recursion depth tracking (used by sub-fmts)   */
/* Sub-formatters call this instead of DscFormat() for nested values.  */
/* ------------------------------------------------------------------ */
int DscFormatValue(const void *data, UINT32 data_len,
                     const dsc_type_t *type, const DscFormatOpts *opts,
                     int depth, DscStrbuf *out);

#endif /* DSC_FORMAT_H */
