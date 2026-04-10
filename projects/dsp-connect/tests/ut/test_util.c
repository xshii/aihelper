/* PURPOSE: Tests for hashmap and strbuf utilities */

#include "test_helper.h"
#include "../src/util/hashmap.h"
#include "../src/util/strbuf.h"

/* ================================================================== */
/* Hashmap tests                                                      */
/* ================================================================== */

TEST(hashmap_put_and_get)
{
    dsc_hashmap_t map;
    dsc_hashmap_init(&map, 16);

    int val_a = 42;
    int val_b = 99;
    ASSERT_EQ(dsc_hashmap_put(&map, "key_a", &val_a), 0);
    ASSERT_EQ(dsc_hashmap_put(&map, "key_b", &val_b), 0);

    ASSERT_EQ(dsc_hashmap_get(&map, "key_a"), &val_a);
    ASSERT_EQ(dsc_hashmap_get(&map, "key_b"), &val_b);
    ASSERT_EQ(map.count, (size_t)2);

    dsc_hashmap_free(&map);
}

TEST(hashmap_get_missing_returns_null)
{
    dsc_hashmap_t map;
    dsc_hashmap_init(&map, 16);

    ASSERT_NULL(dsc_hashmap_get(&map, "nonexistent"));

    int val = 1;
    dsc_hashmap_put(&map, "exists", &val);
    ASSERT_NULL(dsc_hashmap_get(&map, "nope"));

    dsc_hashmap_free(&map);
}

TEST(hashmap_overwrite_existing_key)
{
    dsc_hashmap_t map;
    dsc_hashmap_init(&map, 16);

    int old_val = 10;
    int new_val = 20;
    dsc_hashmap_put(&map, "key", &old_val);
    dsc_hashmap_put(&map, "key", &new_val);

    ASSERT_EQ(dsc_hashmap_get(&map, "key"), &new_val);
    ASSERT_EQ(map.count, (size_t)1);

    dsc_hashmap_free(&map);
}

TEST(hashmap_delete_existing)
{
    dsc_hashmap_t map;
    dsc_hashmap_init(&map, 16);

    int val = 42;
    dsc_hashmap_put(&map, "key", &val);
    ASSERT_EQ(dsc_hashmap_del(&map, "key"), 1);
    ASSERT_NULL(dsc_hashmap_get(&map, "key"));
    ASSERT_EQ(map.count, (size_t)0);

    dsc_hashmap_free(&map);
}

TEST(hashmap_delete_missing_returns_zero)
{
    dsc_hashmap_t map;
    dsc_hashmap_init(&map, 16);

    ASSERT_EQ(dsc_hashmap_del(&map, "nope"), 0);

    dsc_hashmap_free(&map);
}

TEST(hashmap_handles_collisions)
{
    dsc_hashmap_t map;
    dsc_hashmap_init(&map, 4);  /* small capacity forces collisions */

    int vals[20];
    char keys[20][16];
    for (int i = 0; i < 20; i++) {
        vals[i] = i * 10;
        snprintf(keys[i], sizeof(keys[i]), "item_%d", i);
        ASSERT_EQ(dsc_hashmap_put(&map, keys[i], &vals[i]), 0);
    }

    for (int i = 0; i < 20; i++) {
        int *got = (int *)dsc_hashmap_get(&map, keys[i]);
        ASSERT_NOT_NULL(got);
        ASSERT_EQ(*got, i * 10);
    }

    dsc_hashmap_free(&map);
}

TEST(hashmap_clear)
{
    dsc_hashmap_t map;
    dsc_hashmap_init(&map, 16);

    int a = 1, b = 2;
    dsc_hashmap_put(&map, "a", &a);
    dsc_hashmap_put(&map, "b", &b);
    dsc_hashmap_clear(&map);

    ASSERT_EQ(map.count, (size_t)0);
    ASSERT_NULL(dsc_hashmap_get(&map, "a"));
    ASSERT_NULL(dsc_hashmap_get(&map, "b"));

    dsc_hashmap_free(&map);
}

/* ================================================================== */
/* Strbuf tests                                                       */
/* ================================================================== */

TEST(strbuf_append)
{
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 64);

    dsc_strbuf_append(&sb, "hello");
    dsc_strbuf_append(&sb, " world");
    ASSERT_STR_EQ(dsc_strbuf_cstr(&sb), "hello world");
    ASSERT_EQ(sb.len, (size_t)11);

    dsc_strbuf_free(&sb);
}

TEST(strbuf_appendf)
{
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 64);

    dsc_strbuf_appendf(&sb, "val=%d hex=0x%X", 42, 255);
    ASSERT_STR_EQ(dsc_strbuf_cstr(&sb), "val=42 hex=0xFF");

    dsc_strbuf_free(&sb);
}

TEST(strbuf_indent)
{
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 64);

    dsc_strbuf_indent(&sb, 3);  /* 3 * 2 = 6 spaces */
    dsc_strbuf_append(&sb, "x");
    ASSERT_STR_EQ(dsc_strbuf_cstr(&sb), "      x");

    dsc_strbuf_free(&sb);
}

TEST(strbuf_reset_keeps_capacity)
{
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 64);

    dsc_strbuf_append(&sb, "some data");
    size_t cap_before = sb.cap;

    dsc_strbuf_reset(&sb);
    ASSERT_EQ(sb.len, (size_t)0);
    ASSERT_STR_EQ(dsc_strbuf_cstr(&sb), "");
    ASSERT_EQ(sb.cap, cap_before);

    dsc_strbuf_free(&sb);
}

TEST(strbuf_appendn)
{
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 64);

    dsc_strbuf_appendn(&sb, "hello world", 5);
    ASSERT_STR_EQ(dsc_strbuf_cstr(&sb), "hello");
    ASSERT_EQ(sb.len, (size_t)5);

    dsc_strbuf_free(&sb);
}

TEST(strbuf_grows_on_large_append)
{
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 64);

    /* Append more than initial capacity */
    for (int i = 0; i < 200; i++) {
        dsc_strbuf_append(&sb, "x");
    }
    ASSERT_EQ(sb.len, (size_t)200);
    /* Verify all chars are 'x' */
    const char *s = dsc_strbuf_cstr(&sb);
    ASSERT_EQ(s[0], 'x');
    ASSERT_EQ(s[199], 'x');
    ASSERT_EQ(s[200], '\0');

    dsc_strbuf_free(&sb);
}

/* ================================================================== */
/* Runner                                                             */
/* ================================================================== */

int test_util_main(void)
{
    printf("=== test_util ===\n");

    RUN_TEST(hashmap_put_and_get);
    RUN_TEST(hashmap_get_missing_returns_null);
    RUN_TEST(hashmap_overwrite_existing_key);
    RUN_TEST(hashmap_delete_existing);
    RUN_TEST(hashmap_delete_missing_returns_zero);
    RUN_TEST(hashmap_handles_collisions);
    RUN_TEST(hashmap_clear);

    RUN_TEST(strbuf_append);
    RUN_TEST(strbuf_appendf);
    RUN_TEST(strbuf_indent);
    RUN_TEST(strbuf_reset_keeps_capacity);
    RUN_TEST(strbuf_appendn);
    RUN_TEST(strbuf_grows_on_large_append);

    TEST_SUMMARY();
}
