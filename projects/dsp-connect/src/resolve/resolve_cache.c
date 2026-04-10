/* PURPOSE: Cache implementation for resolved symbols — store path→result pairs
 * PATTERN: Hashmap wrapper with store-and-invalidate-all semantics
 * FOR: 弱 AI 参考如何做简单的查询结果缓存 */

#include "resolve_cache.h"

#include <stdlib.h>
#include <string.h>

#include "../core/dsc_errors.h"
#include "../util/hashmap.h"
#include "../util/log.h"

/* ------------------------------------------------------------------ */
/* Internal struct                                                    */
/* ------------------------------------------------------------------ */
struct dsc_resolve_cache_t {
    dsc_hashmap_t map;       /* path string → dsc_resolved_t*       */
    size_t        capacity;  /* maximum number of cached entries     */
};

/* ------------------------------------------------------------------ */
/* Lifecycle                                                          */
/* ------------------------------------------------------------------ */
dsc_resolve_cache_t *dsc_resolve_cache_create(size_t capacity)
{
    if (capacity == 0) {
        capacity = 64;
    }

    dsc_resolve_cache_t *cache = calloc(1, sizeof(*cache));
    if (cache == NULL) {
        return NULL;
    }

    dsc_hashmap_init(&cache->map, capacity);
    cache->capacity = capacity;

    DSC_LOG_DEBUG("resolve_cache: created with capacity %zu", capacity);
    return cache;
}

void dsc_resolve_cache_destroy(dsc_resolve_cache_t *cache)
{
    if (cache == NULL) {
        return;
    }

    /* Free all heap-allocated result values */
    for (size_t i = 0; i < cache->map.cap; i++) {
        if (cache->map.entries[i].key != NULL) {
            free(cache->map.entries[i].value);
        }
    }

    dsc_hashmap_free(&cache->map);
    free(cache);
}

/* ------------------------------------------------------------------ */
/* Cache lookup / populate                                            */
/* ------------------------------------------------------------------ */
int dsc_resolve_cached(dsc_resolve_cache_t *cache,
                       const dsc_symtab_t *symtab, const dsc_arch_t *arch,
                       const char *path, dsc_resolved_t *out)
{
    if (cache == NULL || path == NULL || out == NULL) {
        return DSC_ERR_INVALID_ARG;
    }

    /* Step 1: check the cache */
    dsc_resolved_t *cached = dsc_hashmap_get(&cache->map, path);
    if (cached != NULL) {
        *out = *cached;
        DSC_LOG_DEBUG("resolve_cache: hit for '%s'", path);
        return DSC_OK;
    }

    /* Step 2: resolve the path */
    dsc_resolved_t result;
    int rc = dsc_resolve(symtab, arch, path, &result);
    if (rc < 0) {
        return rc;
    }

    /* Step 3: store in cache (skip if at capacity) */
    if (cache->map.count < cache->capacity) {
        dsc_resolved_t *stored = malloc(sizeof(*stored));
        if (stored != NULL) {
            *stored = result;
            if (dsc_hashmap_put(&cache->map, path, stored) < 0) {
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
void dsc_resolve_cache_invalidate(dsc_resolve_cache_t *cache)
{
    if (cache == NULL) {
        return;
    }

    /* Free all heap-allocated result values before clearing keys */
    for (size_t i = 0; i < cache->map.cap; i++) {
        if (cache->map.entries[i].key != NULL) {
            free(cache->map.entries[i].value);
            cache->map.entries[i].value = NULL;
        }
    }

    dsc_hashmap_clear(&cache->map);
    DSC_LOG_DEBUG("resolve_cache: invalidated all entries");
}
