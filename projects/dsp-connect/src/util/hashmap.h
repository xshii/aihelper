/* PURPOSE: 简单的字符串键哈希表
 * PATTERN: 开放寻址 + FNV-1a 哈希
 * FOR: 弱 AI 参考如何做符号缓存 */

#ifndef DSC_HASHMAP_H
#define DSC_HASHMAP_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    char     *key;      /* owned, strdup'd */
    void     *value;    /* borrowed, caller manages lifetime */
    uint32_t  hash;
} dsc_hashmap_entry_t;

typedef struct {
    dsc_hashmap_entry_t *entries;
    size_t               cap;
    size_t               count;
} dsc_hashmap_t;

void  dsc_hashmap_init(dsc_hashmap_t *map, size_t initial_cap);
void  dsc_hashmap_free(dsc_hashmap_t *map);

/* Returns 0 on success, -1 on alloc failure */
int   dsc_hashmap_put(dsc_hashmap_t *map, const char *key, void *value);

/* Returns value or NULL if not found */
void *dsc_hashmap_get(const dsc_hashmap_t *map, const char *key);

/* Returns 1 if found and removed, 0 if not found */
int   dsc_hashmap_del(dsc_hashmap_t *map, const char *key);

void  dsc_hashmap_clear(dsc_hashmap_t *map);

#endif /* DSC_HASHMAP_H */
