/* PURPOSE: Struct/union formatter — field-by-field display with indentation
 * PATTERN: Recursive descent with depth tracking
 * FOR: Weak AI to reference when formatting composite types */

#ifndef DSC_FORMAT_STRUCT_H
#define DSC_FORMAT_STRUCT_H

#include "../dwarf/dwarf_types.h"
#include "../util/strbuf.h"
#include "format.h"

/* Format a struct or union value.
 * type->kind must be DSC_TYPE_STRUCT or DSC_TYPE_UNION.
 * depth = current nesting depth (0 = top-level).
 * Returns DSC_OK on success, negative error code on failure. */
int dsc_format_struct(const void *data, UINT32 data_len,
                      const dsc_type_t *type, const dsc_format_opts_t *opts,
                      int depth, dsc_strbuf_t *out);

#endif /* DSC_FORMAT_STRUCT_H */
