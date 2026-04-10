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
typedef struct DscResolveCache DscResolveCache;

/* ------------------------------------------------------------------ */
/* API                                                                */
/* ------------------------------------------------------------------ */

/* Create a cache with the given maximum capacity.
 * Returns NULL on allocation failure. */
DscResolveCache *DscResolveCacheCreate(UINT32 capacity);

/* Destroy the cache and free all internal storage. Safe to call with NULL. */
void DscResolveCacheDestroy(DscResolveCache *cache);

/* Resolve with caching: returns cached result if available, otherwise
 * calls DscResolve() and stores the result.
 * Returns DSC_OK on success, negative DscError on failure. */
int DscResolveCached(DscResolveCache *cache,
                       const dsc_symtab_t *symtab, const DscArch *arch,
                       const char *path, DscResolved *out);

/* Invalidate all cached entries (e.g. after program reload). */
void DscResolveCacheInvalidate(DscResolveCache *cache);

#endif /* DSC_RESOLVE_CACHE_H */
