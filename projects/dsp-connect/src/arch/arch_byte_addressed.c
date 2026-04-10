/* PURPOSE: Byte-addressed backend — identity address mapping, endian swap only when needed
 * PATTERN: Concrete vtable impl — struct embeds base, ops are static functions
 * FOR: Weak AI to copy as a starting point for new arch backends */

#include <stdlib.h>
#include <string.h>

#include "arch_byte_addressed.h"
#include "arch_factory.h"
#include "../core/dsc_errors.h"
#include "../util/endian.h"

/* --- Private data: extends base with config --- */
typedef struct {
    dsc_arch_t base;          /* MUST be first member */
    int is_big_endian;        /* target endianness */
    int host_is_big_endian;   /* detected at creation time */
} arch_byte_t;

/* --- vtable implementations --- */

static int byte_logical_to_physical(const dsc_arch_t *self, UINT64 logical,
                                    UINT64 *physical)
{
    (void)self;
    /* Byte-addressed: logical == physical, no translation needed */
    *physical = logical;
    return DSC_OK;
}

static int byte_physical_to_logical(const dsc_arch_t *self, UINT64 physical,
                                    UINT64 *logical)
{
    (void)self;
    /* Byte-addressed: physical == logical, no translation needed */
    *logical = physical;
    return DSC_OK;
}

static void byte_swap_endian(const dsc_arch_t *self, void *buf, UINT32 size)
{
    const arch_byte_t *a = (const arch_byte_t *)self;

    /* No swap needed if host and target have the same endianness */
    if (a->host_is_big_endian == a->is_big_endian) {
        return;
    }

    /* Reverse bytes in place */
    dsc_byte_swap(buf, size);
}

static UINT32 byte_min_access_size(const dsc_arch_t *self)
{
    (void)self;
    return 1;  /* byte-addressed: 1 byte */
}

static UINT32 byte_word_size(const dsc_arch_t *self)
{
    (void)self;
    return 1;  /* byte-addressed: addressable unit = 1 byte */
}

static void byte_destroy(dsc_arch_t *self)
{
    free(self);
}

/* --- Shared ops table --- */
static const struct dsc_arch_ops byte_ops = {
    .logical_to_physical = byte_logical_to_physical,
    .physical_to_logical = byte_physical_to_logical,
    .swap_endian         = byte_swap_endian,
    .min_access_size     = byte_min_access_size,
    .word_size           = byte_word_size,
    .destroy             = byte_destroy,
};

/* --- Creator function called by factory --- */
static dsc_arch_t *byte_create(const dsc_arch_config_t *cfg)
{
    arch_byte_t *a = calloc(1, sizeof(*a));
    if (!a) {
        return NULL;
    }

    a->base.ops = &byte_ops;
    a->is_big_endian = cfg ? cfg->is_big_endian : 0;
    a->host_is_big_endian = dsc_host_is_big_endian();

    /* Set name based on endianness */
    if (a->is_big_endian) {
        memcpy(a->base.name, "byte_be", 8);
    } else {
        memcpy(a->base.name, "byte_le", 8);
    }

    return &a->base;
}

/* --- Creator wrappers for each registered name --- */
static dsc_arch_t *byte_le_create(const dsc_arch_config_t *cfg)
{
    dsc_arch_config_t le_cfg = { .word_bits = 8, .is_big_endian = 0, .addr_shift = 0 };
    if (cfg) {
        le_cfg.word_bits = cfg->word_bits ? cfg->word_bits : 8;
        /* Force little-endian */
        le_cfg.is_big_endian = 0;
        le_cfg.addr_shift = cfg->addr_shift;
    }
    return byte_create(&le_cfg);
}

static dsc_arch_t *byte_be_create(const dsc_arch_config_t *cfg)
{
    dsc_arch_config_t be_cfg = { .word_bits = 8, .is_big_endian = 1, .addr_shift = 0 };
    if (cfg) {
        be_cfg.word_bits = cfg->word_bits ? cfg->word_bits : 8;
        /* Force big-endian */
        be_cfg.is_big_endian = 1;
        be_cfg.addr_shift = cfg->addr_shift;
    }
    return byte_create(&be_cfg);
}

/* --- Registration: called by dsc_arch_register_builtins() --- */
void dsc_arch_byte_register(void)
{
    dsc_arch_register("byte_le", byte_le_create);
    dsc_arch_register("byte_be", byte_be_create);
}
