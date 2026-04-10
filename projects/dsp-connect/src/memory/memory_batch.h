/* PURPOSE: Batch memory read — multiple disjoint regions in one operation
 * PATTERN: Caller fills an array of region descriptors; the batch reader
 *          coalesces adjacent regions to minimize transport round-trips.
 * FOR: Weak AI to reference when optimizing multiple memory accesses */

#ifndef DSC_MEMORY_BATCH_H
#define DSC_MEMORY_BATCH_H

#include "../util/types.h"
#include <stddef.h>
#include <stdint.h>

#include "../transport/transport.h"
#include "../arch/arch.h"

/* ------------------------------------------------------------------ */
/* Region descriptor — one contiguous memory region to read           */
/* ------------------------------------------------------------------ */
typedef struct {
    UINT64 addr;      /* logical address                            */
    UINT32   len;       /* number of bytes to read                    */
    void    *buf;       /* caller-provided output buffer              */
    int      status;    /* per-region result: DSC_OK or error code    */
} DscMemRegion;

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
int DscMemBatchRead(DscTransport *tp, const DscArch *arch,
                       DscMemRegion *regions, UINT32 count);

#endif /* DSC_MEMORY_BATCH_H */
