/* PURPOSE: Abstract architecture adapter — hides byte-vs-word addressing and endianness
 * PATTERN: vtable (ops struct) + inline convenience wrappers — same as transport layer
 * FOR: Weak AI to reference when adding new architecture backends */

#ifndef DSC_ARCH_H
#define DSC_ARCH_H

#include "../util/types.h"
#include <stddef.h>
#include <stdint.h>

#include "../core/dsc_errors.h"
#include "../util/dsc_common.h"

/* --- Forward declaration --- */
typedef struct DscArch DscArch;

/* --- Configuration passed to factory --- */
typedef struct {
    int word_bits;       /* 8, 16, 24, 32 — size of one addressable unit */
    int is_big_endian;   /* 1 = target is big-endian, 0 = little-endian  */
    int addr_shift;      /* for word-addressed: logical = physical << shift */
} DscArchConfig;

/* --- vtable: every backend implements these --- */
struct DscArchOps {
    /* Convert logical address (from DWARF) to physical address (for transport) */
    int (*logical_to_physical)(const DscArch *self, UINT64 logical,
                               UINT64 *physical);

    /* Convert physical address back to logical */
    int (*physical_to_logical)(const DscArch *self, UINT64 physical,
                               UINT64 *logical);

    /* Swap endianness of a value buffer (noop if host matches target) */
    void (*swap_endian)(const DscArch *self, void *buf, UINT32 size);

    /* Get minimum addressable unit size in bytes */
    UINT32 (*min_access_size)(const DscArch *self);

    /* Get word size in bytes */
    UINT32 (*word_size)(const DscArch *self);

    /* Destroy and free all resources */
    void (*destroy)(DscArch *self);
};

/* --- Base object: every backend embeds this as first member --- */
struct DscArch {
    const struct DscArchOps *ops;
    char name[32];
};

/* ===================================================================
 * Inline convenience wrappers — callers use these, never touch ops
 * =================================================================== */

static inline int DscArchLogicalToPhysical(const DscArch *a,
                                               UINT64 logical,
                                               UINT64 *physical)
{
    return a->ops->logical_to_physical(a, logical, physical);
}

static inline int DscArchPhysicalToLogical(const DscArch *a,
                                               UINT64 physical,
                                               UINT64 *logical)
{
    return a->ops->physical_to_logical(a, physical, logical);
}

static inline void DscArchSwapEndian(const DscArch *a,
                                        void *buf, UINT32 size)
{
    a->ops->swap_endian(a, buf, size);
}

static inline UINT32 DscArchMinAccessSize(const DscArch *a)
{
    return a->ops->min_access_size(a);
}

static inline UINT32 DscArchWordSize(const DscArch *a)
{
    return a->ops->word_size(a);
}

static inline void DscArchDestroy(DscArch *a)
{
    if (a && a->ops->destroy) {
        a->ops->destroy(a);
    }
}

#endif /* DSC_ARCH_H */
