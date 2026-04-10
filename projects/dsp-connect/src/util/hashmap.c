/* PURPOSE: hashmap 实现 — uthash 薄包装
 * PATTERN: uthash HASH_FIND_STR / HASH_ADD_KEYPTR / HASH_DEL 宏
 * FOR: 弱 AI 参考如何用 uthash 做字符串键哈希表 */

#include "hashmap.h"
#include <stdlib.h>
#include <string.h>

void dsc_hashmap_init(dsc_hashmap_t *map, size_t initial_cap)
{
    (void)initial_cap; /* uthash 自动管理容量 */
    map->head = NULL;
}

void dsc_hashmap_free(dsc_hashmap_t *map)
{
    dsc_hashmap_entry_t *cur, *tmp;
    HASH_ITER(hh, map->head, cur, tmp) {
        HASH_DEL(map->head, cur);
        free(cur->key);
        free(cur);
    }
    map->head = NULL;
}

int dsc_hashmap_put(dsc_hashmap_t *map, const char *key, void *value)
{
    /* 先查是否已存在 */
    dsc_hashmap_entry_t *existing = NULL;
    HASH_FIND_STR(map->head, key, existing);
    if (existing) {
        existing->value = value; /* 更新 */
        return 0;
    }

    /* 新建 entry */
    dsc_hashmap_entry_t *entry = malloc(sizeof(*entry));
    if (!entry) return -1;

    entry->key = strdup(key);
    if (!entry->key) {
        free(entry);
        return -1;
    }
    entry->value = value;

    HASH_ADD_KEYPTR(hh, map->head, entry->key, strlen(entry->key), entry);
    return 0;
}

void *dsc_hashmap_get(const dsc_hashmap_t *map, const char *key)
{
    dsc_hashmap_entry_t *entry = NULL;
    /* uthash 的 HASH_FIND_STR 第一个参数不能是 const，需要 cast */
    HASH_FIND_STR(((dsc_hashmap_t *)map)->head, key, entry);
    return entry ? entry->value : NULL;
}

int dsc_hashmap_del(dsc_hashmap_t *map, const char *key)
{
    dsc_hashmap_entry_t *entry = NULL;
    HASH_FIND_STR(map->head, key, entry);
    if (!entry) return 0;

    HASH_DEL(map->head, entry);
    free(entry->key);
    free(entry);
    return 1;
}

void dsc_hashmap_clear(dsc_hashmap_t *map)
{
    dsc_hashmap_entry_t *cur, *tmp;
    HASH_ITER(hh, map->head, cur, tmp) {
        HASH_DEL(map->head, cur);
        free(cur->key);
        free(cur);
    }
    map->head = NULL;
}

size_t dsc_hashmap_count(const dsc_hashmap_t *map)
{
    return (size_t)HASH_COUNT(((dsc_hashmap_t *)map)->head);
}
