/* PURPOSE: Tests for hashmap and strbuf utilities */

#include "unity/unity.h"
#include "../src/util/hashmap.h"
#include "../src/util/strbuf.h"


/* ================================================================== */
/* Hashmap tests                                                      */
/* ================================================================== */

void hashmap_put_and_get(void)
{
    dsc_hashmap_t map;
    dsc_hashmap_init(&map, 16);

    int val_a = 42;
    int val_b = 99;
    TEST_ASSERT_EQUAL(0, dsc_hashmap_put(&map, "key_a", &val_a));
    TEST_ASSERT_EQUAL(0, dsc_hashmap_put(&map, "key_b", &val_b));

    TEST_ASSERT_EQUAL_PTR(&val_a, dsc_hashmap_get(&map, "key_a"));
    TEST_ASSERT_EQUAL_PTR(&val_b, dsc_hashmap_get(&map, "key_b"));
    TEST_ASSERT_EQUAL_size_t(2, dsc_hashmap_count(&map));

    dsc_hashmap_free(&map);
}

void hashmap_get_missing_returns_null(void)
{
    dsc_hashmap_t map;
    dsc_hashmap_init(&map, 16);

    TEST_ASSERT_NULL(dsc_hashmap_get(&map, "nonexistent"));

    int val = 1;
    dsc_hashmap_put(&map, "exists", &val);
    TEST_ASSERT_NULL(dsc_hashmap_get(&map, "nope"));

    dsc_hashmap_free(&map);
}

void hashmap_overwrite_existing_key(void)
{
    dsc_hashmap_t map;
    dsc_hashmap_init(&map, 16);

    int old_val = 10;
    int new_val = 20;
    dsc_hashmap_put(&map, "key", &old_val);
    dsc_hashmap_put(&map, "key", &new_val);

    TEST_ASSERT_EQUAL_PTR(&new_val, dsc_hashmap_get(&map, "key"));
    TEST_ASSERT_EQUAL_size_t(1, dsc_hashmap_count(&map));

    dsc_hashmap_free(&map);
}

void hashmap_delete_existing(void)
{
    dsc_hashmap_t map;
    dsc_hashmap_init(&map, 16);

    int val = 42;
    dsc_hashmap_put(&map, "key", &val);
    TEST_ASSERT_EQUAL(1, dsc_hashmap_del(&map, "key"));
    TEST_ASSERT_NULL(dsc_hashmap_get(&map, "key"));
    TEST_ASSERT_EQUAL_size_t(0, dsc_hashmap_count(&map));

    dsc_hashmap_free(&map);
}

void hashmap_delete_missing_returns_zero(void)
{
    dsc_hashmap_t map;
    dsc_hashmap_init(&map, 16);

    TEST_ASSERT_EQUAL(0, dsc_hashmap_del(&map, "nope"));

    dsc_hashmap_free(&map);
}

void hashmap_handles_collisions(void)
{
    dsc_hashmap_t map;
    dsc_hashmap_init(&map, 4);  /* small capacity forces collisions */

    int vals[20];
    char keys[20][16];
    for (int i = 0; i < 20; i++) {
        vals[i] = i * 10;
        snprintf(keys[i], sizeof(keys[i]), "item_%d", i);
        TEST_ASSERT_EQUAL(0, dsc_hashmap_put(&map, keys[i], &vals[i]));
    }

    for (int i = 0; i < 20; i++) {
        int *got = (int *)dsc_hashmap_get(&map, keys[i]);
        TEST_ASSERT_NOT_NULL(got);
        TEST_ASSERT_EQUAL(i * 10, *got);
    }

    dsc_hashmap_free(&map);
}

void hashmap_clear(void)
{
    dsc_hashmap_t map;
    dsc_hashmap_init(&map, 16);

    int a = 1, b = 2;
    dsc_hashmap_put(&map, "a", &a);
    dsc_hashmap_put(&map, "b", &b);
    dsc_hashmap_clear(&map);

    TEST_ASSERT_EQUAL_size_t(0, dsc_hashmap_count(&map));
    TEST_ASSERT_NULL(dsc_hashmap_get(&map, "a"));
    TEST_ASSERT_NULL(dsc_hashmap_get(&map, "b"));

    dsc_hashmap_free(&map);
}

/* ================================================================== */
/* Strbuf tests                                                       */
/* ================================================================== */

void strbuf_append(void)
{
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 64);

    dsc_strbuf_append(&sb, "hello");
    dsc_strbuf_append(&sb, " world");
    TEST_ASSERT_EQUAL_STRING("hello world", dsc_strbuf_cstr(&sb));
    TEST_ASSERT_EQUAL_size_t(11, sb.len);

    dsc_strbuf_free(&sb);
}

void strbuf_appendf(void)
{
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 64);

    dsc_strbuf_appendf(&sb, "val=%d hex=0x%X", 42, 255);
    TEST_ASSERT_EQUAL_STRING("val=42 hex=0xFF", dsc_strbuf_cstr(&sb));

    dsc_strbuf_free(&sb);
}

void strbuf_indent(void)
{
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 64);

    dsc_strbuf_indent(&sb, 3);  /* 3 * 2 = 6 spaces */
    dsc_strbuf_append(&sb, "x");
    TEST_ASSERT_EQUAL_STRING("      x", dsc_strbuf_cstr(&sb));

    dsc_strbuf_free(&sb);
}

void strbuf_reset_keeps_capacity(void)
{
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 64);

    dsc_strbuf_append(&sb, "some data");
    size_t cap_before = sb.cap;

    dsc_strbuf_reset(&sb);
    TEST_ASSERT_EQUAL_size_t(0, sb.len);
    TEST_ASSERT_EQUAL_STRING("", dsc_strbuf_cstr(&sb));
    TEST_ASSERT_EQUAL_size_t(cap_before, sb.cap);

    dsc_strbuf_free(&sb);
}

void strbuf_appendn(void)
{
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 64);

    dsc_strbuf_appendn(&sb, "hello world", 5);
    TEST_ASSERT_EQUAL_STRING("hello", dsc_strbuf_cstr(&sb));
    TEST_ASSERT_EQUAL_size_t(5, sb.len);

    dsc_strbuf_free(&sb);
}

void strbuf_grows_on_large_append(void)
{
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 64);

    /* Append more than initial capacity */
    for (int i = 0; i < 200; i++) {
        dsc_strbuf_append(&sb, "x");
    }
    TEST_ASSERT_EQUAL_size_t(200, sb.len);
    /* Verify all chars are 'x' */
    const char *s = dsc_strbuf_cstr(&sb);
    TEST_ASSERT_EQUAL('x', s[0]);
    TEST_ASSERT_EQUAL('x', s[199]);
    TEST_ASSERT_EQUAL('\0', s[200]);

    dsc_strbuf_free(&sb);
}

/* ================================================================== */
/* Runner                                                             */
/* ================================================================== */

int test_util_main(void)
{
    UNITY_BEGIN();

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

    return UNITY_END();
}
