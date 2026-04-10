/* PURPOSE: Mock arch implementations — identity and word16 presets */

#include "mock_arch.h"
#include "../../src/core/dsc_errors.h"
#include <string.h>

/* ================================================================== */
/* Identity arch: byte-addressed, no translation, no endian swap      */
/* ================================================================== */

static int id_logical_to_physical(const dsc_arch_t *self,
                                  uint64_t logical, uint64_t *physical)
{
    (void)self;
    *physical = logical;
    return DSC_OK;
}

static int id_physical_to_logical(const dsc_arch_t *self,
                                  uint64_t physical, uint64_t *logical)
{
    (void)self;
    *logical = physical;
    return DSC_OK;
}

static void id_swap_endian(const dsc_arch_t *self, void *buf, size_t size)
{
    (void)self; (void)buf; (void)size;
    /* No swap — identity arch assumes host == target endianness */
}

static size_t id_min_access(const dsc_arch_t *self)
{
    (void)self;
    return 1;
}

static size_t id_word_size(const dsc_arch_t *self)
{
    (void)self;
    return 1;
}

static void id_destroy(dsc_arch_t *self) { (void)self; }

static const struct dsc_arch_ops identity_ops = {
    .logical_to_physical = id_logical_to_physical,
    .physical_to_logical = id_physical_to_logical,
    .swap_endian         = id_swap_endian,
    .min_access_size     = id_min_access,
    .word_size           = id_word_size,
    .destroy             = id_destroy,
};

static dsc_arch_t s_identity = {
    .ops  = &identity_ops,
    .name = "mock_identity",
};

dsc_arch_t *mock_arch_identity(void)
{
    return &s_identity;
}

/* ================================================================== */
/* Word16 arch: 16-bit words, logical = physical * 2                  */
/* ================================================================== */

static int w16_logical_to_physical(const dsc_arch_t *self,
                                   uint64_t logical, uint64_t *physical)
{
    (void)self;
    if (logical % 2 != 0) {
        return DSC_ERR_MEM_ALIGN;
    }
    *physical = logical >> 1;
    return DSC_OK;
}

static int w16_physical_to_logical(const dsc_arch_t *self,
                                   uint64_t physical, uint64_t *logical)
{
    (void)self;
    *logical = physical << 1;
    return DSC_OK;
}

static void w16_swap_endian(const dsc_arch_t *self, void *buf, size_t size)
{
    (void)self; (void)buf; (void)size;
    /* No swap — mock assumes host matches target */
}

static size_t w16_min_access(const dsc_arch_t *self)
{
    (void)self;
    return 2;
}

static size_t w16_word_size(const dsc_arch_t *self)
{
    (void)self;
    return 2;
}

static void w16_destroy(dsc_arch_t *self) { (void)self; }

static const struct dsc_arch_ops word16_ops = {
    .logical_to_physical = w16_logical_to_physical,
    .physical_to_logical = w16_physical_to_logical,
    .swap_endian         = w16_swap_endian,
    .min_access_size     = w16_min_access,
    .word_size           = w16_word_size,
    .destroy             = w16_destroy,
};

static dsc_arch_t s_word16 = {
    .ops  = &word16_ops,
    .name = "mock_word16",
};

dsc_arch_t *mock_arch_word16(void)
{
    return &s_word16;
}
