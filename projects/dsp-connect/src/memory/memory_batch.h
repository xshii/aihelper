/* PURPOSE: Batch memory read — multiple disjoint regions in one operation
 * PATTERN: Caller fills an array of region descriptors; the batch reader
 *          coalesces adjacent regions to minimize transport round-trips.
 * FOR: Weak AI to reference when optimizing multiple memory accesses */

#ifndef DSC_MEMORY_BATCH_H
#define DSC_MEMORY_BATCH_H

#include <stddef.h>
#include <stdint.h>

#include "../transport/transport.h"
#include "../arch/arch.h"

/* ------------------------------------------------------------------ */
/* Region descriptor — one contiguous memory region to read           */
/* ------------------------------------------------------------------ */
typedef struct {
    uint64_t addr;      /* logical address                            */
    size_t   len;       /* number of bytes to read                    */
    void    *buf;       /* caller-provided output buffer              */
    int      status;    /* per-region result: DSC_OK or error code    */
} dsc_mem_region_t;

/* ------------------------------------------------------------------ */
/* API                                                                */
/* ------------------------------------------------------------------ */

/* Batch read: read multiple disjoint memory regions efficiently.
 *
 * The implementation sorts regions by address, coalesces adjacent or
 * overlapping ranges into fewer transport reads, and distributes the
 * data back into each region's buffer.
 *
 * Each region's `status` field is set individually — some regions may
 * succeed while others fail.
 *
 * Returns DSC_OK if all regions succeeded, or the first error code
 * encountered (individual statuses are still set). */
int dsc_mem_batch_read(dsc_transport_t *tp, const dsc_arch_t *arch,
                       dsc_mem_region_t *regions, size_t count);

#endif /* DSC_MEMORY_BATCH_H */
