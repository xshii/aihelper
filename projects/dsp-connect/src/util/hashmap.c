/* PURPOSE: hashmap 实现 — uthash 薄包装
 * PATTERN: uthash HASH_FIND_STR / HASH_ADD_KEYPTR / HASH_DEL 宏
 * FOR: 弱 AI 参考如何用 uthash 做字符串键哈希表 */

#include <stdlib.h>
#include <string.h>

#include "hashmap.h"

void DscHashmapInit(DscHashmap *map, UINT32 initial_cap)
{
    (void)initial_cap; /* uthash 自动管理容量 */
    map->head = NULL;
}

void DscHashmapFree(DscHashmap *map)
{
    DscHashmapEntry *cur, *tmp;
    HASH_ITER(hh, map->head, cur, tmp) {
        HASH_DEL(map->head, cur);
        free(cur->key);
        free(cur);
    }
    map->head = NULL;
}

int DscHashmapPut(DscHashmap *map, const char *key, void *value)
{
    /* 先查是否已存在 */
    DscHashmapEntry *existing = NULL;
    HASH_FIND_STR(map->head, key, existing);
    if (existing) {
        existing->value = value; /* 更新 */
        return 0;
    }

    /* 新建 entry */
    DscHashmapEntry *entry = malloc(sizeof(*entry));
    if (!entry) {
        return -1;
    }

    entry->key = strdup(key);
    if (!entry->key) {
        free(entry);
        return -1;
    }
    entry->value = value;

    HASH_ADD_KEYPTR(hh, map->head, entry->key, strlen(entry->key), entry);
    return 0;
}

void *DscHashmapGet(const DscHashmap *map, const char *key)
{
    DscHashmapEntry *entry = NULL;
    /* uthash 的 HASH_FIND_STR 第一个参数不能是 const，需要 cast */
    HASH_FIND_STR(((DscHashmap *)map)->head, key, entry);
    return entry ? entry->value : NULL;
}

int DscHashmapDel(DscHashmap *map, const char *key)
{
    DscHashmapEntry *entry = NULL;
    HASH_FIND_STR(map->head, key, entry);
    if (!entry) {
        return 0;
    }

    HASH_DEL(map->head, entry);
    free(entry->key);
    free(entry);
    return 1;
}

void DscHashmapClear(DscHashmap *map)
{
    DscHashmapEntry *cur, *tmp;
    HASH_ITER(hh, map->head, cur, tmp) {
        HASH_DEL(map->head, cur);
        free(cur->key);
        free(cur);
    }
    map->head = NULL;
}

UINT32 DscHashmapCount(const DscHashmap *map)
{
    return (UINT32)HASH_COUNT(((DscHashmap *)map)->head);
}
