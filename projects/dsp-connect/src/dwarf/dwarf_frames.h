/* PURPOSE: Call frame information (CFI) from DWARF .debug_frame / .eh_frame
 * PATTERN: Opaque table + register-based unwinding API
 * FOR: Weak AI to reference when implementing stack unwinding */

#ifndef DSC_DWARF_FRAMES_H
#define DSC_DWARF_FRAMES_H

#include <stddef.h>
#include <stdint.h>

#include "dwarf_parser.h"

/* ------------------------------------------------------------------ */
/* Register set — enough for common architectures                     */
/* ------------------------------------------------------------------ */
#define DSC_MAX_REGS 32

typedef struct {
    UINT64 regs[DSC_MAX_REGS];
    UINT64 cfa;   /* canonical frame address */
    UINT64 pc;    /* program counter / return address */
} dsc_regset_t;

/* ------------------------------------------------------------------ */
/* X-macro: CFA rule kinds                                            */
/* ------------------------------------------------------------------ */
#define DSC_CFA_RULE_TABLE(X) \
    X(DSC_CFA_REG_OFFSET,  "reg+offset")  \
    X(DSC_CFA_EXPRESSION,  "expression")   \
    X(DSC_CFA_UNDEFINED,   "undefined")

#define X_ENUM(name, str) name,
typedef enum {
    DSC_CFA_RULE_TABLE(X_ENUM)
    DSC_CFA_RULE_COUNT
} dsc_cfa_rule_kind_t;
#undef X_ENUM

/* ------------------------------------------------------------------ */
/* Frame description entry (FDE)                                      */
/* ------------------------------------------------------------------ */
typedef struct {
    UINT64            pc_start;     /* start of address range */
    UINT64            pc_end;       /* end of address range (exclusive) */
    dsc_cfa_rule_kind_t cfa_rule;
    int                 cfa_reg;      /* base register for CFA */
    INT64             cfa_offset;   /* offset from base register */
} dsc_frame_entry_t;

/* ------------------------------------------------------------------ */
/* Frame table                                                        */
/* ------------------------------------------------------------------ */
typedef struct {
    dsc_frame_entry_t *entries;
    UINT32             count;
    UINT32             cap;
} dsc_frames_t;

/* ------------------------------------------------------------------ */
/* API                                                                */
/* ------------------------------------------------------------------ */

/* Initialize an empty frame table */
void dsc_frames_init(dsc_frames_t *frames);

/* Free all entries */
void dsc_frames_free(dsc_frames_t *frames);

/* Load frame information from DWARF.
 * Returns 0 on success, negative dsc_error_t on failure. */
int dsc_frames_load(dsc_frames_t *frames, dsc_dwarf_t *dw);

/* Unwind one frame: given registers at `addr`, compute the caller's registers.
 * `regs` is updated in-place.
 * Returns 0 on success, DSC_ERR_NOT_FOUND if no FDE covers `addr`. */
int dsc_frames_unwind(const dsc_frames_t *frames, UINT64 addr,
                      dsc_regset_t *regs);

/* Returns the CFA rule name string (from X-macro) */
const char *dsc_cfa_rule_name(dsc_cfa_rule_kind_t kind);

/* Number of frame entries */
UINT32 dsc_frames_count(const dsc_frames_t *frames);

#endif /* DSC_DWARF_FRAMES_H */
