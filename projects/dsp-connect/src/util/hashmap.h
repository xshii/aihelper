/* PURPOSE: 字符串键哈希表 — 基于 uthash 的薄包装
 * PATTERN: uthash (header-only, 业界标准) + 简化的 init/put/get/del API
 * FOR: 弱 AI 参考如何用 uthash 做 O(1) 键值缓存 */

#ifndef DSC_HASHMAP_H
#define DSC_HASHMAP_H

#include "types.h"
#include "uthash.h"

/* uthash 要求 hash handle 嵌入结构体，
 * 这个 entry 是内部实现，外部只通过 dsc_hashmap_* API 操作 */
typedef struct dsc_hashmap_entry_t {
    char            *key;   /* owned, strdup'd */
    void            *value; /* borrowed, caller manages lifetime */
    UT_hash_handle   hh;    /* uthash bookkeeping */
} dsc_hashmap_entry_t;

/* 哈希表句柄 — 实际上就是 uthash 的头指针 */
typedef struct {
    dsc_hashmap_entry_t *head; /* uthash head pointer (NULL = empty) */
} dsc_hashmap_t;

/* Create / destroy */
void  dsc_hashmap_init(dsc_hashmap_t *map, UINT32 initial_cap);
void  dsc_hashmap_free(dsc_hashmap_t *map);

/* Returns 0 on success, -1 on alloc failure */
int   dsc_hashmap_put(dsc_hashmap_t *map, const char *key, void *value);

/* Returns value or NULL if not found */
void *dsc_hashmap_get(const dsc_hashmap_t *map, const char *key);

/* Returns 1 if found and removed, 0 if not found */
int   dsc_hashmap_del(dsc_hashmap_t *map, const char *key);

/* Remove all entries (frees keys, not values) */
void  dsc_hashmap_clear(dsc_hashmap_t *map);

/* Entry count */
UINT32 dsc_hashmap_count(const dsc_hashmap_t *map);

#endif /* DSC_HASHMAP_H */
