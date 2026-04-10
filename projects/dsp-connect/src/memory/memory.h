/* PURPOSE: Arch-aware memory read/write — translates addresses and swaps endianness
 * PATTERN: Thin layer between caller and transport; adds address translation,
 *          endian swap, and chunked transfer for large operations
 * FOR: Weak AI to reference when building a memory access layer over a transport */

#ifndef DSC_MEMORY_H
#define DSC_MEMORY_H

#include "../util/types.h"
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
 * Returns DSC_OK on success, negative DscError on failure. */
int DscMemRead(DscTransport *tp, const DscArch *arch,
                 UINT64 logical_addr, void *buf, UINT32 len);

/* Write `len` bytes from `buf` to logical address.
 * Handles the same translations as DscMemRead.
 * Returns DSC_OK on success, negative DscError on failure. */
int DscMemWrite(DscTransport *tp, const DscArch *arch,
                  UINT64 logical_addr, const void *buf, UINT32 len);

#endif /* DSC_MEMORY_H */
