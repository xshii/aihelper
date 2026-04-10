/* PURPOSE: Word-addressed backend — address translation and sub-word access for DSPs
 * PATTERN: Concrete vtable impl with configurable word size (16/24/32-bit)
 * FOR: Weak AI to reference when dealing with word-addressed DSP architectures
 *
 * KEY CONCEPT:
 *   On word-addressed DSPs, each address points to a WORD, not a byte.
 *   DWARF debug info uses byte-like logical addresses.
 *   Transport uses physical word addresses.
 *
 *   Example (16-bit word DSP):
 *     logical byte address 0x100  -> physical word address 0x80
 *     logical byte address 0x102  -> physical word address 0x81
 *     Because: physical = logical / word_bytes
 *              logical  = physical * word_bytes
 */

#include <stdlib.h>
#include <string.h>

#include "arch_word_addressed.h"
#include "arch_factory.h"
#include "../core/dsc_errors.h"
#include "../util/endian.h"

/* --- Private data: extends base with word config --- */
typedef struct {
    DscArch base;            /* MUST be first member */
    int word_bytes;             /* word size: 2, 3, or 4 bytes */
    int is_big_endian;          /* target endianness */
    int host_is_big_endian;     /* detected at creation time */
    int addr_shift;             /* bits to shift: log2(word_bytes) or custom */
} arch_word_t;

/* --- Compute default addr_shift from word_bytes --- */
static int default_shift_for_word_bytes(int word_bytes)
{
    /* For power-of-2 sizes, shift = log2(word_bytes)
     * For non-power-of-2 (e.g. 3-byte/24-bit), we use division instead of shift.
     * Return 0 to signal "use division". */
    switch (word_bytes) {
    case 2: return 1;  /* logical >> 1 = physical */
    case 4: return 2;  /* logical >> 2 = physical */
    default: return 0; /* use multiplication/division */
    }
}

/* --- vtable implementations --- */

static int word_logical_to_physical(const DscArch *self, UINT64 logical,
                                    UINT64 *physical)
{
    const arch_word_t *a = (const arch_word_t *)self;

    /* Check alignment: logical address must be on a word boundary */
    if (logical % (UINT64)a->word_bytes != 0) {
        return DSC_ERR_MEM_ALIGN;
    }

    if (a->addr_shift > 0) {
        /* Fast path: power-of-2 word size, use shift */
        *physical = logical >> a->addr_shift;
    } else {
        /* Slow path: non-power-of-2 (e.g. 24-bit), use division */
        *physical = logical / (UINT64)a->word_bytes;
    }
    return DSC_OK;
}

static int word_physical_to_logical(const DscArch *self, UINT64 physical,
                                    UINT64 *logical)
{
    const arch_word_t *a = (const arch_word_t *)self;

    if (a->addr_shift > 0) {
        *logical = physical << a->addr_shift;
    } else {
        *logical = physical * (UINT64)a->word_bytes;
    }
    return DSC_OK;
}

static void word_swap_endian(const DscArch *self, void *buf, UINT32 size)
{
    const arch_word_t *a = (const arch_word_t *)self;

    /* No swap needed if host and target have the same endianness */
    if (a->host_is_big_endian == a->is_big_endian) {
        return;
    }

    /* Swap each word-sized chunk independently.
     * For a 4-byte buffer on a 16-bit word DSP, swap two 2-byte words. */
    UINT32 ws = (UINT32)a->word_bytes;
    UINT8 *p = (UINT8 *)buf;

    UINT32 offset = 0;
    while (offset + ws <= size) {
        DscByteSwap(p + offset, ws);
        offset += ws;
    }
    /* Remaining bytes (partial word) are left as-is */
}

static UINT32 word_min_access_size(const DscArch *self)
{
    const arch_word_t *a = (const arch_word_t *)self;
    /* Minimum access = one full word, because sub-word byte access
     * is not directly supported on word-addressed architectures */
    return (UINT32)a->word_bytes;
}

static UINT32 word_word_size(const DscArch *self)
{
    const arch_word_t *a = (const arch_word_t *)self;
    return (UINT32)a->word_bytes;
}

static void word_destroy(DscArch *self)
{
    free(self);
}

/* --- Shared ops table --- */
static const struct DscArchOps word_ops = {
    .logical_to_physical = word_logical_to_physical,
    .physical_to_logical = word_physical_to_logical,
    .swap_endian         = word_swap_endian,
    .min_access_size     = word_min_access_size,
    .word_size           = word_word_size,
    .destroy             = word_destroy,
};

/* --- Generic creator --- */
static DscArch *word_create_with(int word_bytes, int is_big_endian,
                                    int addr_shift, const char *name)
{
    arch_word_t *a = calloc(1, sizeof(*a));
    if (!a) {
        return NULL;
    }

    a->base.ops = &word_ops;
    a->word_bytes = word_bytes;
    a->is_big_endian = is_big_endian;
    a->host_is_big_endian = DscHostIsBigEndian();

    /* Use caller-specified shift, or compute default */
    if (addr_shift > 0) {
        a->addr_shift = addr_shift;
    } else {
        a->addr_shift = default_shift_for_word_bytes(word_bytes);
    }

    UINT32 len = strlen(name);
    if (len >= sizeof(a->base.name)) {
        len = sizeof(a->base.name) - 1;
    }
    memcpy(a->base.name, name, len);
    a->base.name[len] = '\0';

    return &a->base;
}

/* --- Creator functions for each registered name --- */

static DscArch *word16_create(const DscArchConfig *cfg)
{
    int big_endian = cfg ? cfg->is_big_endian : 1;  /* DSPs are often big-endian */
    int shift = cfg ? cfg->addr_shift : 0;
    return word_create_with(2, big_endian, shift, "word16");
}

static DscArch *word24_create(const DscArchConfig *cfg)
{
    int big_endian = cfg ? cfg->is_big_endian : 1;
    int shift = cfg ? cfg->addr_shift : 0;
    return word_create_with(3, big_endian, shift, "word24");
}

static DscArch *word32_create(const DscArchConfig *cfg)
{
    int big_endian = cfg ? cfg->is_big_endian : 1;
    int shift = cfg ? cfg->addr_shift : 0;
    return word_create_with(4, big_endian, shift, "word32");
}

/* --- Registration: called by DscArchRegisterBuiltins() --- */
void DscArchWordRegister(void)
{
    DscArchRegister("word16", word16_create);
    DscArchRegister("word24", word24_create);
    DscArchRegister("word32", word32_create);
}
