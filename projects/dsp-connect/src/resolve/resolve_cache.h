/* PURPOSE: Cache layer for resolved symbols — avoids repeated path parsing
 * PATTERN: Opaque struct + create/destroy lifecycle; delegates to hashmap
 * FOR: Weak AI to reference when adding caching to a lookup-heavy module */

#ifndef DSC_RESOLVE_CACHE_H
#define DSC_RESOLVE_CACHE_H

#include "../util/types.h"
#include <stddef.h>

#include "resolve.h"

/* ------------------------------------------------------------------ */
/* Opaque cache handle                                                */
/* ------------------------------------------------------------------ */
typedef struct dsc_resolve_cache_t dsc_resolve_cache_t;

/* ------------------------------------------------------------------ */
/* API                                                                */
/* ------------------------------------------------------------------ */

/* Create a cache with the given maximum capacity.
 * Returns NULL on allocation failure. */
dsc_resolve_cache_t *dsc_resolve_cache_create(UINT32 capacity);

/* Destroy the cache and free all internal storage. Safe to call with NULL. */
void dsc_resolve_cache_destroy(dsc_resolve_cache_t *cache);

/* Resolve with caching: returns cached result if available, otherwise
 * calls dsc_resolve() and stores the result.
 * Returns DSC_OK on success, negative dsc_error_t on failure. */
int dsc_resolve_cached(dsc_resolve_cache_t *cache,
                       const dsc_symtab_t *symtab, const dsc_arch_t *arch,
                       const char *path, dsc_resolved_t *out);

/* Invalidate all cached entries (e.g. after program reload). */
void dsc_resolve_cache_invalidate(dsc_resolve_cache_t *cache);

#endif /* DSC_RESOLVE_CACHE_H */
