/* PURPOSE: Line table implementation — binary search over sorted entries
 * PATTERN: Conditional compilation, DSC_TRY, qsort + bsearch
 * FOR: Weak AI to reference when mapping addresses to source locations */

#include <stdlib.h>
#include <string.h>

#include "dwarf_lines.h"
#include "../core/dsc_errors.h"
#include "../util/dsc_common.h"
#include "../util/log.h"

#define INITIAL_CAP 256

/* ------------------------------------------------------------------ */
/* Init / Free                                                        */
/* ------------------------------------------------------------------ */

void dsc_lines_init(dsc_lines_t *lines)
{
    lines->entries = NULL;
    lines->count   = 0;
    lines->cap     = 0;
}

void dsc_lines_free(dsc_lines_t *lines)
{
    if (!lines) return;

    for (size_t i = 0; i < lines->count; i++) {
        free(lines->entries[i].file);
    }
    free(lines->entries);

    lines->entries = NULL;
    lines->count   = 0;
    lines->cap     = 0;
}

/* ------------------------------------------------------------------ */
/* Load                                                               */
/* ------------------------------------------------------------------ */

#ifdef DSC_USE_LIBDWARF

#include <dwarf.h>
#include <libdwarf.h>

/* ------------------------------------------------------------------ */
/* Internal: add one entry                                            */
/* ------------------------------------------------------------------ */
static int add_entry(dsc_lines_t *lines, uint64_t addr,
                     const char *file, int line, int column)
{
    if (lines->count >= lines->cap) {
        size_t new_cap = (lines->cap == 0) ? INITIAL_CAP : lines->cap * 2;
        dsc_line_entry_t *new_buf = realloc(lines->entries,
                                            new_cap * sizeof(dsc_line_entry_t));
        if (!new_buf) {
            return DSC_ERR_NOMEM;
        }
        lines->entries = new_buf;
        lines->cap     = new_cap;
    }

    dsc_line_entry_t *e = &lines->entries[lines->count];
    e->addr   = addr;
    e->file   = file ? strdup(file) : NULL;
    e->line   = line;
    e->column = column;

    if (file && !e->file) {
        return DSC_ERR_NOMEM;
    }

    lines->count++;
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Comparator for sorting by address                                  */
/* ------------------------------------------------------------------ */
static int cmp_by_addr(const void *a, const void *b)
{
    const dsc_line_entry_t *ea = (const dsc_line_entry_t *)a;
    const dsc_line_entry_t *eb = (const dsc_line_entry_t *)b;

    if (ea->addr < eb->addr) return -1;
    if (ea->addr > eb->addr) return  1;
    return 0;
}

/* Process a single line context entry: extract addr/file/line/col and store */
static int process_line_entry(dsc_lines_t *lines, Dwarf_Debug dbg,
                              Dwarf_Line line_ctx, Dwarf_Error *err)
{
    Dwarf_Addr addr = 0;
    Dwarf_Unsigned lineno = 0;
    Dwarf_Signed colno = 0;
    char *src = NULL;

    dwarf_lineaddr(line_ctx, &addr, err);
    dwarf_lineno(line_ctx, &lineno, err);
    dwarf_lineoff_b(line_ctx, &colno, err);
    dwarf_linesrc(line_ctx, &src, err);

    int rc = add_entry(lines, (uint64_t)addr, src,
                       (int)lineno, (int)colno);

    if (src) {
        dwarf_dealloc(dbg, src, DW_DLA_STRING);
    }
    return rc;
}

/* Iterate all CUs, collecting line table entries into `lines` */
static int load_cu_lines(dsc_lines_t *lines, Dwarf_Debug dbg)
{
    Dwarf_Error err = NULL;
    Dwarf_Unsigned cu_header_length, abbrev_offset, next_cu_header;
    Dwarf_Half version_stamp, address_size;

    while (dwarf_next_cu_header(dbg, &cu_header_length, &version_stamp,
                                &abbrev_offset, &address_size,
                                &next_cu_header, &err) == DW_DLV_OK)
    {
        Dwarf_Die cu_die = NULL;
        if (dwarf_siblingof(dbg, NULL, &cu_die, &err) != DW_DLV_OK) {
            continue;
        }

        Dwarf_Line *linebuf = NULL;
        Dwarf_Signed linecount = 0;

        if (dwarf_srclines(cu_die, &linebuf, &linecount, &err) != DW_DLV_OK) {
            dwarf_dealloc(dbg, cu_die, DW_DLA_DIE);
            continue;
        }

        for (Dwarf_Signed i = 0; i < linecount; i++) {
            DSC_TRY(process_line_entry(lines, dbg, linebuf[i], &err));
        }

        dwarf_srclines_dealloc(dbg, linebuf, linecount);
        dwarf_dealloc(dbg, cu_die, DW_DLA_DIE);
    }
    return DSC_OK;
}

int dsc_lines_load(dsc_lines_t *lines, dsc_dwarf_t *dw)
{
    if (!lines || !dw) return DSC_ERR_INVALID_ARG;

    /* Access the internal libdwarf handle via accessor */
    extern Dwarf_Debug dsc_dwarf_get_dbg(dsc_dwarf_t *dw);
    Dwarf_Debug dbg = dsc_dwarf_get_dbg(dw);
    if (!dbg) return DSC_ERR_DWARF_INIT;

    DSC_TRY(load_cu_lines(lines, dbg));

    /* Sort for binary search */
    if (lines->count > 1) {
        qsort(lines->entries, lines->count,
              sizeof(dsc_line_entry_t), cmp_by_addr);
    }

    DSC_LOG_INFO("loaded %zu line entries", lines->count);
    return DSC_OK;
}

#else /* !DSC_USE_LIBDWARF */

int dsc_lines_load(dsc_lines_t *lines, dsc_dwarf_t *dw)
{
    (void)dw;
    if (!lines) return DSC_ERR_INVALID_ARG;
    DSC_LOG_WARN("stub: no line info loaded (libdwarf not available)");
    return DSC_OK;
}

#endif /* DSC_USE_LIBDWARF */

/* ------------------------------------------------------------------ */
/* Lookup — binary search for the largest addr <= target              */
/* ------------------------------------------------------------------ */

int dsc_lines_lookup(const dsc_lines_t *lines, uint64_t addr,
                     dsc_line_info_t *out)
{
    if (!lines || !out || lines->count == 0) {
        return DSC_ERR_NOT_FOUND;
    }

    /* Binary search: find the last entry with entry->addr <= addr */
    size_t lo = 0;
    size_t hi = lines->count;

    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;
        if (lines->entries[mid].addr <= addr) {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }

    /* lo is now the index of the first entry with addr > target.
     * The match is at lo - 1, if it exists. */
    if (lo == 0) {
        return DSC_ERR_NOT_FOUND;
    }

    const dsc_line_entry_t *e = &lines->entries[lo - 1];
    out->file   = e->file;
    out->line   = e->line;
    out->column = e->column;
    return DSC_OK;
}

size_t dsc_lines_count(const dsc_lines_t *lines)
{
    return lines ? lines->count : 0;
}
