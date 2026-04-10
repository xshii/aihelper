/* PURPOSE: 字符串键哈希表 — 基于 uthash 的薄包装
 * PATTERN: uthash (header-only, 业界标准) + 简化的 init/put/get/del API
 * FOR: 弱 AI 参考如何用 uthash 做 O(1) 键值缓存 */

#ifndef DSC_HASHMAP_H
#define DSC_HASHMAP_H

#include "types.h"
#include "uthash.h"

/* uthash 要求 hash handle 嵌入结构体，
 * 这个 entry 是内部实现，外部只通过 dsc_hashmap_* API 操作 */
typedef struct DscHashmapEntry {
    char            *key;   /* owned, strdup'd */
    void            *value; /* borrowed, caller manages lifetime */
    UT_hash_handle   hh;    /* uthash bookkeeping */
} DscHashmapEntry;

/* 哈希表句柄 — 实际上就是 uthash 的头指针 */
typedef struct {
    DscHashmapEntry *head; /* uthash head pointer (NULL = empty) */
} DscHashmap;

/* Create / destroy */
void  DscHashmapInit(DscHashmap *map, UINT32 initial_cap);
void  DscHashmapFree(DscHashmap *map);

/* Returns 0 on success, -1 on alloc failure */
int   DscHashmapPut(DscHashmap *map, const char *key, void *value);

/* Returns value or NULL if not found */
void *DscHashmapGet(const DscHashmap *map, const char *key);

/* Returns 1 if found and removed, 0 if not found */
int   DscHashmapDel(DscHashmap *map, const char *key);

/* Remove all entries (frees keys, not values) */
void  DscHashmapClear(DscHashmap *map);

/* Entry count */
UINT32 DscHashmapCount(const DscHashmap *map);

#endif /* DSC_HASHMAP_H */
