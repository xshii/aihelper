/* PURPOSE: Batch memory read — sort, coalesce, read, scatter
 * PATTERN: Three-phase pipeline:
 *          (1) Sort region indices by address
 *          (2) Coalesce adjacent/overlapping regions into merged spans
 *          (3) Read each merged span, then scatter bytes into per-region buffers
 *          This minimizes transport round-trips for many small reads.
 * FOR: 弱 AI 参考如何做散列聚合(scatter-gather)内存读取 */

#include <stdlib.h>
#include <string.h>

#include "memory_batch.h"
#include "../core/dsc_errors.h"
#include "../util/log.h"

/* Maximum gap (in bytes) between two regions to still coalesce them.
 * If two regions are within this distance, we read the gap too and discard it.
 * This avoids many tiny reads at the cost of reading a few extra bytes. */
#define COALESCE_GAP_MAX 64

/* ------------------------------------------------------------------ */
/* Internal: a merged span covering one or more original regions      */
/* ------------------------------------------------------------------ */
typedef struct {
    UINT64 start;     /* lowest physical address in the span        */
    UINT64 end;       /* one past highest byte in the span          */
    UINT32  *indices;   /* indices into the original regions array    */
    UINT32   index_count;
    UINT32   index_cap;
} merged_span_t;

/* ------------------------------------------------------------------ */
/* Internal: comparison for qsort — sort by address ascending         */
/* ------------------------------------------------------------------ */
typedef struct {
    UINT64 addr;
    UINT32   original_index;
} sort_entry_t;

static int cmp_sort_entry(const void *a, const void *b)
{
    const sort_entry_t *ea = (const sort_entry_t *)a;
    const sort_entry_t *eb = (const sort_entry_t *)b;
    if (ea->addr < eb->addr) {
        return -1;
    }
    if (ea->addr > eb->addr) {
        return 1;
    }
    return 0;
}

/* ------------------------------------------------------------------ */
/* Internal: add an index to a merged span                            */
/* ------------------------------------------------------------------ */
static int span_add_index(merged_span_t *span, UINT32 idx)
{
    if (span->index_count >= span->index_cap) {
        UINT32 new_cap = (span->index_cap == 0) ? 4 : span->index_cap * 2;
        UINT32 *new_arr = realloc(span->indices, new_cap * sizeof(UINT32));
        if (new_arr == NULL) {
            return DSC_ERR_NOMEM;
        }
        span->indices = new_arr;
        span->index_cap = new_cap;
    }
    span->indices[span->index_count++] = idx;
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Internal: free an array of merged spans                            */
/* ------------------------------------------------------------------ */
static void free_spans(merged_span_t *spans, UINT32 count)
{
    for (UINT32 i = 0; i < count; i++) {
        free(spans[i].indices);
    }
    free(spans);
}

/* ------------------------------------------------------------------ */
/* Public API                                                         */
/* ------------------------------------------------------------------ */
int DscMemBatchRead(DscTransport *tp, const DscArch *arch,
                       DscMemRegion *regions, UINT32 count)
{
    /* Three-phase batch read:
     *   Phase 1: Sort region indices by start address
     *   Phase 2: Coalesce adjacent regions (within COALESCE_GAP_MAX gap) into merged spans
     *   Phase 3: Read each span in one transport call, scatter bytes to per-region buffers
     * This minimizes round-trips: N regions → M merged reads (M <= N). */
    (void)arch;
    if (tp == NULL || regions == NULL) {
        return DSC_ERR_INVALID_ARG;
    }
    if (count == 0) {
        return DSC_OK;
    }

    /* Initialize all statuses to OK */
    for (UINT32 i = 0; i < count; i++) {
        regions[i].status = DSC_OK;
    }

    /* ============================================================== */
    /* Phase 1: sort regions by address                               */
    /* ============================================================== */
    sort_entry_t *sorted = malloc(count * sizeof(sort_entry_t));
    if (sorted == NULL) {
        return DSC_ERR_NOMEM;
    }
    for (UINT32 i = 0; i < count; i++) {
        sorted[i].addr = regions[i].addr;
        sorted[i].original_index = i;
    }
    qsort(sorted, count, sizeof(sort_entry_t), cmp_sort_entry);

    /* ============================================================== */
    /* Phase 2: coalesce into merged spans                            */
    /* ============================================================== */
    /* Worst case: no coalescing, one span per region */
    merged_span_t *spans = calloc(count, sizeof(merged_span_t));
    if (spans == NULL) {
        free(sorted);
        return DSC_ERR_NOMEM;
    }
    UINT32 span_count = 0;

    for (UINT32 i = 0; i < count; i++) {
        UINT32 ri = sorted[i].original_index;
        UINT64 r_start = regions[ri].addr;
        UINT64 r_end   = regions[ri].addr + regions[ri].len;

        /* Try to extend the current span */
        if (span_count > 0) {
            merged_span_t *cur = &spans[span_count - 1];
            /* Coalesce if this region overlaps or is within the gap threshold */
            if (r_start <= cur->end + COALESCE_GAP_MAX) {
                if (r_end > cur->end) {
                    cur->end = r_end;
                }
                int rc = span_add_index(cur, ri);
                if (rc < 0) {
                    free_spans(spans, span_count);
                    free(sorted);
                    return rc;
                }
                continue;
            }
        }

        /* Start a new span */
        merged_span_t *ns = &spans[span_count];
        ns->start = r_start;
        ns->end   = r_end;
        ns->indices = NULL;
        ns->index_count = 0;
        ns->index_cap = 0;
        int rc = span_add_index(ns, ri);
        if (rc < 0) {
            free_spans(spans, span_count);
            free(sorted);
            return rc;
        }
        span_count++;
    }

    free(sorted);
    sorted = NULL;

    DSC_LOG_DEBUG("mem_batch_read: %zu regions coalesced into %zu spans",
                  count, span_count);

    /* ============================================================== */
    /* Phase 3: read each span and scatter into region buffers        */
    /* ============================================================== */
    int first_error = DSC_OK;

    for (UINT32 s = 0; s < span_count; s++) {
        merged_span_t *span = &spans[s];
        UINT32 span_len = (UINT32)(span->end - span->start);

        /* Allocate a temporary buffer for the merged read */
        UINT8 *tmp = malloc(span_len);
        if (tmp == NULL) {
            /* Mark all regions in this span as failed */
            for (UINT32 j = 0; j < span->index_count; j++) {
                regions[span->indices[j]].status = DSC_ERR_NOMEM;
            }
            if (first_error == DSC_OK) {
                first_error = DSC_ERR_NOMEM;
            }
            continue;
        }

        /* Read the entire span.
         * Use DscMemRead which handles address translation and chunking.
         * NOTE: we pass the raw span bytes without per-element endian swap,
         * since each region may represent a different data type. Callers are
         * responsible for endian handling at the value interpretation level. */
        int rc = DscTransportMemRead(tp, span->start, tmp, span_len);
        if (rc < 0) {
            DSC_LOG_ERROR("mem_batch_read: span read failed at 0x%llx len=%zu",
                          (unsigned long long)span->start, span_len);
            for (UINT32 j = 0; j < span->index_count; j++) {
                regions[span->indices[j]].status = DSC_ERR_MEM_READ;
            }
            if (first_error == DSC_OK) {
                first_error = DSC_ERR_MEM_READ;
            }
            free(tmp);
            continue;
        }

        /* Scatter: copy each region's portion from the merged buffer */
        for (UINT32 j = 0; j < span->index_count; j++) {
            UINT32 ri = span->indices[j];
            UINT64 offset = regions[ri].addr - span->start;
            if (regions[ri].buf != NULL && regions[ri].len > 0) {
                memcpy(regions[ri].buf, tmp + offset, regions[ri].len);
                regions[ri].status = DSC_OK;
            }
        }

        free(tmp);
    }

    free_spans(spans, span_count);
    return first_error;
}
