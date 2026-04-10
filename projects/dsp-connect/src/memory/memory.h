/* PURPOSE: Arch-aware memory read/write — translates addresses and swaps endianness
 * PATTERN: Thin layer between caller and transport; adds address translation,
 *          endian swap, and chunked transfer for large operations
 * FOR: Weak AI to reference when building a memory access layer over a transport */

#ifndef DSC_MEMORY_H
#define DSC_MEMORY_H

#include <stddef.h>
#include <stdint.h>

#include "../transport/transport.h"
#include "../arch/arch.h"

/* ------------------------------------------------------------------ */
/* API                                                                */
/* ------------------------------------------------------------------ */

/* Read `len` bytes from logical address into `buf`.
 * Handles:
 *   - Logical → physical address translation via arch
 *   - Chunked reads if len exceeds transport max chunk size
 *   - Endianness swap via arch
 * Returns DSC_OK on success, negative dsc_error_t on failure. */
int dsc_mem_read(dsc_transport_t *tp, const dsc_arch_t *arch,
                 uint64_t logical_addr, void *buf, size_t len);

/* Write `len` bytes from `buf` to logical address.
 * Handles the same translations as dsc_mem_read.
 * Returns DSC_OK on success, negative dsc_error_t on failure. */
int dsc_mem_write(dsc_transport_t *tp, const dsc_arch_t *arch,
                  uint64_t logical_addr, const void *buf, size_t len);

#endif /* DSC_MEMORY_H */
