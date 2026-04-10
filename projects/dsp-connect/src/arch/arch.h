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
typedef struct dsc_arch_t dsc_arch_t;

/* --- Configuration passed to factory --- */
typedef struct {
    int word_bits;       /* 8, 16, 24, 32 — size of one addressable unit */
    int is_big_endian;   /* 1 = target is big-endian, 0 = little-endian  */
    int addr_shift;      /* for word-addressed: logical = physical << shift */
} dsc_arch_config_t;

/* --- vtable: every backend implements these --- */
struct dsc_arch_ops {
    /* Convert logical address (from DWARF) to physical address (for transport) */
    int (*logical_to_physical)(const dsc_arch_t *self, UINT64 logical,
                               UINT64 *physical);

    /* Convert physical address back to logical */
    int (*physical_to_logical)(const dsc_arch_t *self, UINT64 physical,
                               UINT64 *logical);

    /* Swap endianness of a value buffer (noop if host matches target) */
    void (*swap_endian)(const dsc_arch_t *self, void *buf, UINT32 size);

    /* Get minimum addressable unit size in bytes */
    UINT32 (*min_access_size)(const dsc_arch_t *self);

    /* Get word size in bytes */
    UINT32 (*word_size)(const dsc_arch_t *self);

    /* Destroy and free all resources */
    void (*destroy)(dsc_arch_t *self);
};

/* --- Base object: every backend embeds this as first member --- */
struct dsc_arch_t {
    const struct dsc_arch_ops *ops;
    char name[32];
};

/* ===================================================================
 * Inline convenience wrappers — callers use these, never touch ops
 * =================================================================== */

static inline int dsc_arch_logical_to_physical(const dsc_arch_t *a,
                                               UINT64 logical,
                                               UINT64 *physical)
{
    return a->ops->logical_to_physical(a, logical, physical);
}

static inline int dsc_arch_physical_to_logical(const dsc_arch_t *a,
                                               UINT64 physical,
                                               UINT64 *logical)
{
    return a->ops->physical_to_logical(a, physical, logical);
}

static inline void dsc_arch_swap_endian(const dsc_arch_t *a,
                                        void *buf, UINT32 size)
{
    a->ops->swap_endian(a, buf, size);
}

static inline UINT32 dsc_arch_min_access_size(const dsc_arch_t *a)
{
    return a->ops->min_access_size(a);
}

static inline UINT32 dsc_arch_word_size(const dsc_arch_t *a)
{
    return a->ops->word_size(a);
}

static inline void dsc_arch_destroy(dsc_arch_t *a)
{
    if (a && a->ops->destroy) {
        a->ops->destroy(a);
    }
}

#endif /* DSC_ARCH_H */
