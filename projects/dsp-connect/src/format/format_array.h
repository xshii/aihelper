/* PURPOSE: Array formatter — element-by-element display with index labels
 * PATTERN: Loop over elements, delegate each to dsc_format_value, hex dump fallback
 * FOR: Weak AI to reference when displaying arrays from raw bytes */

#ifndef DSC_FORMAT_ARRAY_H
#define DSC_FORMAT_ARRAY_H

#include "../dwarf/dwarf_types.h"
#include "../util/strbuf.h"
#include "format.h"

/* Format an array value.
 * type->kind must be DSC_TYPE_ARRAY.
 * Respects opts->array_max_elems for truncation.
 * Falls back to hex dump for char/uint8 arrays.
 * Returns DSC_OK on success, negative error code on failure. */
int dsc_format_array(const void *data, UINT32 data_len,
                     const dsc_type_t *type, const dsc_format_opts_t *opts,
                     int depth, dsc_strbuf_t *out);

#endif /* DSC_FORMAT_ARRAY_H */
