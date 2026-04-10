/* PURPOSE: Cache implementation for resolved symbols — store path→result pairs
 * PATTERN: Hashmap wrapper with store-and-invalidate-all semantics
 * FOR: 弱 AI 参考如何做简单的查询结果缓存 */

#include <stdlib.h>
#include <string.h>

#include "resolve_cache.h"
#include "../core/dsc_errors.h"
#include "../util/hashmap.h"
#include "../util/log.h"

/* ------------------------------------------------------------------ */
/* Internal struct                                                    */
/* ------------------------------------------------------------------ */
struct DscResolveCache {
    DscHashmap map;       /* path string → DscResolved*       */
    UINT32        capacity;  /* maximum number of cached entries     */
};

/* ------------------------------------------------------------------ */
/* Lifecycle                                                          */
/* ------------------------------------------------------------------ */
DscResolveCache *DscResolveCacheCreate(UINT32 capacity)
{
    if (capacity == 0) {
        capacity = 64;
    }

    DscResolveCache *cache = calloc(1, sizeof(*cache));
    if (cache == NULL) {
        return NULL;
    }

    DscHashmapInit(&cache->map, capacity);
    cache->capacity = capacity;

    DSC_LOG_DEBUG("resolve_cache: created with capacity %zu", capacity);
    return cache;
}

/* Free all heap-allocated result values stored in the cache */
static void free_cached_values(DscHashmap *map)
{
    DscHashmapEntry *cur, *tmp;
    HASH_ITER(hh, map->head, cur, tmp) {
        free(cur->value); /* free the DscResolved* */
    }
}

void DscResolveCacheDestroy(DscResolveCache *cache)
{
    if (cache == NULL) {
        return;
    }
    free_cached_values(&cache->map);
    DscHashmapFree(&cache->map);
    free(cache);
}

/* ------------------------------------------------------------------ */
/* Cache lookup / populate                                            */
/* ------------------------------------------------------------------ */
int DscResolveCached(DscResolveCache *cache,
                       const dsc_symtab_t *symtab, const DscArch *arch,
                       const char *path, DscResolved *out)
{
    if (cache == NULL || path == NULL || out == NULL) {
        return DSC_ERR_INVALID_ARG;
    }

    /* Step 1: check the cache */
    DscResolved *cached = DscHashmapGet(&cache->map, path);
    if (cached != NULL) {
        *out = *cached;
        DSC_LOG_DEBUG("resolve_cache: hit for '%s'", path);
        return DSC_OK;
    }

    /* Step 2: resolve the path */
    DscResolved result;
    int rc = DscResolve(symtab, arch, path, &result);
    if (rc < 0) {
        return rc;
    }

    /* Step 3: store in cache (skip if at capacity) */
    if (DscHashmapCount(&cache->map) < cache->capacity) {
        DscResolved *stored = malloc(sizeof(*stored));
        if (stored != NULL) {
            *stored = result;
            if (DscHashmapPut(&cache->map, path, stored) < 0) {
                free(stored);
                /* Non-fatal: we still have the result, just not cached */
                DSC_LOG_WARN("resolve_cache: failed to store '%s'", path);
            } else {
                DSC_LOG_DEBUG("resolve_cache: stored '%s'", path);
            }
        }
    }

    *out = result;
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Invalidation                                                       */
/* ------------------------------------------------------------------ */
void DscResolveCacheInvalidate(DscResolveCache *cache)
{
    if (cache == NULL) {
        return;
    }

    free_cached_values(&cache->map);
    DscHashmapClear(&cache->map);
    DSC_LOG_DEBUG("resolve_cache: invalidated all entries");
}
