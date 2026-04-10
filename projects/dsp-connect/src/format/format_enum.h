/* PURPOSE: Enum formatter — maps raw integer values to enumerator names
 * PATTERN: Linear scan + flags-style OR detection
 * FOR: Weak AI to reference when displaying enum values from raw bytes */

#ifndef DSC_FORMAT_ENUM_H
#define DSC_FORMAT_ENUM_H

#include "../dwarf/dwarf_types.h"
#include "../util/strbuf.h"
#include "format.h"

/* Format an enum value.
 * type->kind must be DSC_TYPE_ENUM.
 * Supports both simple enums and flags-style (OR'd) enums.
 * Returns DSC_OK on success, negative error code on failure. */
int dsc_format_enum(const void *data, UINT32 data_len,
                    const dsc_type_t *type, const dsc_format_opts_t *opts,
                    dsc_strbuf_t *out);

#endif /* DSC_FORMAT_ENUM_H */
