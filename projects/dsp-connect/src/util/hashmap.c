/* PURPOSE: hashmap 实现 — FNV-1a + 线性探测
 * PATTERN: Open-addressing hash map with linear probing and auto-resize
 * FOR: 弱 AI 参考如何做 O(1) 键值缓存 */

#include "hashmap.h"
#include <stdlib.h>
#include <string.h>

#define LOAD_FACTOR_PERCENT 70

static uint32_t fnv1a(const char *key)
{
    uint32_t h = 2166136261u;
    for (const char *p = key; *p; p++) {
        h ^= (uint8_t)*p;
        h *= 16777619u;
    }
    return h;
}

static size_t probe(const dsc_hashmap_t *map, uint32_t hash)
{
    return hash & (map->cap - 1); /* cap is always power of 2 */
}

static int grow(dsc_hashmap_t *map)
{
    size_t old_cap = map->cap;
    dsc_hashmap_entry_t *old = map->entries;

    size_t new_cap = old_cap * 2;
    dsc_hashmap_entry_t *new_entries = calloc(new_cap, sizeof(dsc_hashmap_entry_t));
    if (!new_entries) return -1;

    map->entries = new_entries;
    map->cap = new_cap;
    map->count = 0;

    for (size_t i = 0; i < old_cap; i++) {
        if (old[i].key) {
            dsc_hashmap_put(map, old[i].key, old[i].value);
            free(old[i].key);
        }
    }
    free(old);
    return 0;
}

void dsc_hashmap_init(dsc_hashmap_t *map, size_t initial_cap)
{
    /* Round up to power of 2 */
    size_t cap = 16;
    while (cap < initial_cap) cap *= 2;

    map->entries = calloc(cap, sizeof(dsc_hashmap_entry_t));
    map->cap = cap;
    map->count = 0;
}

void dsc_hashmap_free(dsc_hashmap_t *map)
{
    for (size_t i = 0; i < map->cap; i++) {
        free(map->entries[i].key);
    }
    free(map->entries);
    map->entries = NULL;
    map->cap = 0;
    map->count = 0;
}

int dsc_hashmap_put(dsc_hashmap_t *map, const char *key, void *value)
{
    if (map->count * 100 / map->cap >= LOAD_FACTOR_PERCENT) {
        if (grow(map) != 0) return -1;
    }

    uint32_t h = fnv1a(key);
    size_t idx = probe(map, h);

    while (map->entries[idx].key) {
        if (map->entries[idx].hash == h &&
            strcmp(map->entries[idx].key, key) == 0) {
            /* Update existing */
            map->entries[idx].value = value;
            return 0;
        }
        idx = (idx + 1) & (map->cap - 1);
    }

    map->entries[idx].key = strdup(key);
    if (!map->entries[idx].key) return -1;
    map->entries[idx].value = value;
    map->entries[idx].hash = h;
    map->count++;
    return 0;
}

void *dsc_hashmap_get(const dsc_hashmap_t *map, const char *key)
{
    uint32_t h = fnv1a(key);
    size_t idx = probe(map, h);

    while (map->entries[idx].key) {
        if (map->entries[idx].hash == h &&
            strcmp(map->entries[idx].key, key) == 0) {
            return map->entries[idx].value;
        }
        idx = (idx + 1) & (map->cap - 1);
    }
    return NULL;
}

int dsc_hashmap_del(dsc_hashmap_t *map, const char *key)
{
    uint32_t h = fnv1a(key);
    size_t idx = probe(map, h);

    while (map->entries[idx].key) {
        if (map->entries[idx].hash == h &&
            strcmp(map->entries[idx].key, key) == 0) {
            free(map->entries[idx].key);
            map->entries[idx].key = NULL;
            map->entries[idx].value = NULL;
            map->count--;
            /* Rehash subsequent entries in cluster */
            size_t next = (idx + 1) & (map->cap - 1);
            while (map->entries[next].key) {
                char *k = map->entries[next].key;
                void *v = map->entries[next].value;
                map->entries[next].key = NULL;
                map->entries[next].value = NULL;
                map->count--;
                dsc_hashmap_put(map, k, v);
                free(k);
                next = (next + 1) & (map->cap - 1);
            }
            return 1;
        }
        idx = (idx + 1) & (map->cap - 1);
    }
    return 0;
}

void dsc_hashmap_clear(dsc_hashmap_t *map)
{
    for (size_t i = 0; i < map->cap; i++) {
        free(map->entries[i].key);
        map->entries[i].key = NULL;
        map->entries[i].value = NULL;
    }
    map->count = 0;
}
