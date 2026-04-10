/* PURPOSE: Call frame unwinding — sorted FDE table with binary search
 * PATTERN: Conditional compilation, DSC_TRY, X-macro string table
 * FOR: Weak AI to reference when implementing CFA-based stack unwinding */

#include "dwarf_frames.h"
#include "../core/dsc_errors.h"
#include "../util/log.h"
#include "../util/dsc_common.h"

#include <stdlib.h>
#include <string.h>

#define INITIAL_CAP 128

/* ------------------------------------------------------------------ */
/* X-macro → string table for CFA rule names                          */
/* ------------------------------------------------------------------ */

#define X_STR(name, str) [name] = str,
static const char *cfa_rule_names[DSC_CFA_RULE_COUNT] = {
    DSC_CFA_RULE_TABLE(X_STR)
};
#undef X_STR

const char *dsc_cfa_rule_name(dsc_cfa_rule_kind_t kind)
{
    if (kind >= 0 && kind < DSC_CFA_RULE_COUNT) {
        return cfa_rule_names[kind];
    }
    return "unknown";
}

/* ------------------------------------------------------------------ */
/* Init / Free                                                        */
/* ------------------------------------------------------------------ */

void dsc_frames_init(dsc_frames_t *frames)
{
    frames->entries = NULL;
    frames->count   = 0;
    frames->cap     = 0;
}

void dsc_frames_free(dsc_frames_t *frames)
{
    if (!frames) return;
    free(frames->entries);
    frames->entries = NULL;
    frames->count   = 0;
    frames->cap     = 0;
}

/* ------------------------------------------------------------------ */
/* Load                                                               */
/* ------------------------------------------------------------------ */

#ifdef DSC_USE_LIBDWARF

#include <dwarf.h>
#include <libdwarf.h>

/* ------------------------------------------------------------------ */
/* Internal: add one FDE                                              */
/* ------------------------------------------------------------------ */
static int add_fde(dsc_frames_t *frames, uint64_t pc_start, uint64_t pc_end,
                   dsc_cfa_rule_kind_t rule, int reg, int64_t offset)
{
    if (frames->count >= frames->cap) {
        size_t new_cap = (frames->cap == 0) ? INITIAL_CAP : frames->cap * 2;
        dsc_frame_entry_t *new_buf = realloc(frames->entries,
                                             new_cap * sizeof(dsc_frame_entry_t));
        if (!new_buf) {
            return DSC_ERR_NOMEM;
        }
        frames->entries = new_buf;
        frames->cap     = new_cap;
    }

    dsc_frame_entry_t *e = &frames->entries[frames->count++];
    e->pc_start  = pc_start;
    e->pc_end    = pc_end;
    e->cfa_rule  = rule;
    e->cfa_reg   = reg;
    e->cfa_offset = offset;
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Comparator for sorting by pc_start                                 */
/* ------------------------------------------------------------------ */
static int cmp_by_pc(const void *a, const void *b)
{
    const dsc_frame_entry_t *fa = (const dsc_frame_entry_t *)a;
    const dsc_frame_entry_t *fb = (const dsc_frame_entry_t *)b;

    if (fa->pc_start < fb->pc_start) return -1;
    if (fa->pc_start > fb->pc_start) return  1;
    return 0;
}

/* Process a single FDE: extract PC range and store with default CFA rule */
static int process_one_fde(dsc_frames_t *frames, Dwarf_Fde fde,
                           Dwarf_Error *err)
{
    Dwarf_Addr low_pc = 0;
    Dwarf_Unsigned func_length = 0;
    Dwarf_Ptr fde_bytes = NULL;
    Dwarf_Unsigned fde_byte_length = 0;
    Dwarf_Off cie_offset = 0;
    Dwarf_Signed cie_index = 0;
    Dwarf_Off fde_offset = 0;

    if (dwarf_get_fde_range(fde, &low_pc, &func_length,
                            &fde_bytes, &fde_byte_length,
                            &cie_offset, &cie_index,
                            &fde_offset, err) != DW_DLV_OK) {
        return DSC_OK; /* skip this FDE, not fatal */
    }

    /* Default to reg+offset rule — a full implementation would
     * evaluate the CFA instructions per row. */
    return add_fde(frames, (uint64_t)low_pc,
                   (uint64_t)(low_pc + func_length),
                   DSC_CFA_REG_OFFSET, 0, 0);
}

/* Iterate all FDEs from the CIE/FDE list and collect frame entries */
static int load_fde_list(dsc_frames_t *frames, Dwarf_Debug dbg)
{
    Dwarf_Error err = NULL;
    Dwarf_Cie *cie_data = NULL;
    Dwarf_Signed cie_count = 0;
    Dwarf_Fde *fde_data = NULL;
    Dwarf_Signed fde_count = 0;

    int res = dwarf_get_fde_list(dbg, &cie_data, &cie_count,
                                  &fde_data, &fde_count, &err);
    if (res != DW_DLV_OK) {
        /* Try .eh_frame instead */
        res = dwarf_get_fde_list_eh(dbg, &cie_data, &cie_count,
                                     &fde_data, &fde_count, &err);
        if (res != DW_DLV_OK) {
            DSC_LOG_WARN("no frame data found");
            return DSC_OK;
        }
    }

    for (Dwarf_Signed i = 0; i < fde_count; i++) {
        DSC_TRY(process_one_fde(frames, fde_data[i], &err));
    }

    dwarf_fde_cie_list_dealloc(dbg, cie_data, cie_count,
                                fde_data, fde_count);
    return DSC_OK;
}

int dsc_frames_load(dsc_frames_t *frames, dsc_dwarf_t *dw)
{
    if (!frames || !dw) return DSC_ERR_INVALID_ARG;

    /* Access the internal libdwarf handle via accessor */
    extern Dwarf_Debug dsc_dwarf_get_dbg(dsc_dwarf_t *dw);
    Dwarf_Debug dbg = dsc_dwarf_get_dbg(dw);
    if (!dbg) return DSC_ERR_DWARF_INIT;

    DSC_TRY(load_fde_list(frames, dbg));

    /* Sort for binary search */
    if (frames->count > 1) {
        qsort(frames->entries, frames->count,
              sizeof(dsc_frame_entry_t), cmp_by_pc);
    }

    DSC_LOG_INFO("loaded %zu frame entries", frames->count);
    return DSC_OK;
}

#else /* !DSC_USE_LIBDWARF */

int dsc_frames_load(dsc_frames_t *frames, dsc_dwarf_t *dw)
{
    (void)dw;
    if (!frames) return DSC_ERR_INVALID_ARG;
    DSC_LOG_WARN("stub: no frame info loaded (libdwarf not available)");
    return DSC_OK;
}

#endif /* DSC_USE_LIBDWARF */

/* ------------------------------------------------------------------ */
/* Unwind — find FDE for addr, apply CFA rule to compute caller regs  */
/* ------------------------------------------------------------------ */

/* Internal: find the FDE that covers `addr` using binary search */
static const dsc_frame_entry_t *find_fde(const dsc_frames_t *frames,
                                         uint64_t addr)
{
    if (!frames || frames->count == 0) {
        return NULL;
    }

    /* Binary search: find the last entry with pc_start <= addr */
    size_t lo = 0;
    size_t hi = frames->count;

    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;
        if (frames->entries[mid].pc_start <= addr) {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }

    if (lo == 0) {
        return NULL;
    }

    const dsc_frame_entry_t *fde = &frames->entries[lo - 1];

    /* Verify addr is within the FDE's range */
    if (addr >= fde->pc_end) {
        return NULL;
    }

    return fde;
}

int dsc_frames_unwind(const dsc_frames_t *frames, uint64_t addr,
                      dsc_regset_t *regs)
{
    if (!frames || !regs) {
        return DSC_ERR_INVALID_ARG;
    }

    const dsc_frame_entry_t *fde = find_fde(frames, addr);
    if (!fde) {
        return DSC_ERR_NOT_FOUND;
    }

    switch (fde->cfa_rule) {
    case DSC_CFA_REG_OFFSET:
        /* CFA = reg[cfa_reg] + cfa_offset
         * This is the most common rule for standard call frames.
         * The return address is at CFA - pointer_size (simplified). */
        if (fde->cfa_reg >= 0 && fde->cfa_reg < DSC_MAX_REGS) {
            regs->cfa = regs->regs[fde->cfa_reg] + (uint64_t)fde->cfa_offset;
        }
        /* In a real implementation, we would read the return address from
         * memory at (CFA - ptr_size) and set regs->pc accordingly.
         * For this demo, we just update the CFA. */
        break;

    case DSC_CFA_EXPRESSION:
        /* DWARF expression evaluation would go here.
         * This is complex and architecture-dependent. */
        DSC_LOG_WARN("CFA expression evaluation not implemented");
        return DSC_ERR_NOT_FOUND;

    case DSC_CFA_UNDEFINED:
        /* End of stack — can't unwind further */
        return DSC_ERR_NOT_FOUND;

    default:
        return DSC_ERR_NOT_FOUND;
    }

    return DSC_OK;
}

size_t dsc_frames_count(const dsc_frames_t *frames)
{
    return frames ? frames->count : 0;
}
