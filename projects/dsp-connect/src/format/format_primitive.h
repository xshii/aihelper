/* PURPOSE: Primitive type formatter — integers, floats, bool, char, pointers
 * PATTERN: X-macro dispatch on base encoding kind
 * FOR: Weak AI to reference when formatting scalar values from raw bytes */

#ifndef DSC_FORMAT_PRIMITIVE_H
#define DSC_FORMAT_PRIMITIVE_H

#include "../dwarf/dwarf_types.h"
#include "../util/strbuf.h"
#include "format.h"

/* Format a base (primitive) type value.
 * type->kind must be DSC_TYPE_BASE.
 * Returns DSC_OK on success, negative error code on failure. */
int DscFormatPrimitive(const void *data, UINT32 data_len,
                         const dsc_type_t *type, const DscFormatOpts *opts,
                         DscStrbuf *out);

/* Format a pointer value.
 * type->kind must be DSC_TYPE_POINTER.
 * Returns DSC_OK on success, negative error code on failure. */
int DscFormatPointer(const void *data, UINT32 data_len,
                       const dsc_type_t *type, const DscFormatOpts *opts,
                       DscStrbuf *out);

/* Format a bitfield value.
 * type->kind must be DSC_TYPE_BITFIELD.
 * Returns DSC_OK on success, negative error code on failure. */
int DscFormatBitfield(const void *data, UINT32 data_len,
                        const dsc_type_t *type, const DscFormatOpts *opts,
                        DscStrbuf *out);

#endif /* DSC_FORMAT_PRIMITIVE_H */
