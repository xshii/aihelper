/* PURPOSE: Tests for hashmap and strbuf utilities */

#include "unity/unity.h"
#include "../src/util/hashmap.h"
#include "../src/util/strbuf.h"


/* ================================================================== */
/* Hashmap tests                                                      */
/* ================================================================== */

void hashmap_put_and_get(void)
{
    DscHashmap map;
    DscHashmapInit(&map, 16);

    int val_a = 42;
    int val_b = 99;
    TEST_ASSERT_EQUAL(0, DscHashmapPut(&map, "key_a", &val_a));
    TEST_ASSERT_EQUAL(0, DscHashmapPut(&map, "key_b", &val_b));

    TEST_ASSERT_EQUAL_PTR(&val_a, DscHashmapGet(&map, "key_a"));
    TEST_ASSERT_EQUAL_PTR(&val_b, DscHashmapGet(&map, "key_b"));
    TEST_ASSERT_EQUAL_size_t(2, DscHashmapCount(&map));

    DscHashmapFree(&map);
}

void hashmap_get_missing_returns_null(void)
{
    DscHashmap map;
    DscHashmapInit(&map, 16);

    TEST_ASSERT_NULL(DscHashmapGet(&map, "nonexistent"));

    int val = 1;
    DscHashmapPut(&map, "exists", &val);
    TEST_ASSERT_NULL(DscHashmapGet(&map, "nope"));

    DscHashmapFree(&map);
}

void hashmap_overwrite_existing_key(void)
{
    DscHashmap map;
    DscHashmapInit(&map, 16);

    int old_val = 10;
    int new_val = 20;
    DscHashmapPut(&map, "key", &old_val);
    DscHashmapPut(&map, "key", &new_val);

    TEST_ASSERT_EQUAL_PTR(&new_val, DscHashmapGet(&map, "key"));
    TEST_ASSERT_EQUAL_size_t(1, DscHashmapCount(&map));

    DscHashmapFree(&map);
}

void hashmap_delete_existing(void)
{
    DscHashmap map;
    DscHashmapInit(&map, 16);

    int val = 42;
    DscHashmapPut(&map, "key", &val);
    TEST_ASSERT_EQUAL(1, DscHashmapDel(&map, "key"));
    TEST_ASSERT_NULL(DscHashmapGet(&map, "key"));
    TEST_ASSERT_EQUAL_size_t(0, DscHashmapCount(&map));

    DscHashmapFree(&map);
}

void hashmap_delete_missing_returns_zero(void)
{
    DscHashmap map;
    DscHashmapInit(&map, 16);

    TEST_ASSERT_EQUAL(0, DscHashmapDel(&map, "nope"));

    DscHashmapFree(&map);
}

void hashmap_handles_collisions(void)
{
    DscHashmap map;
    DscHashmapInit(&map, 4);  /* small capacity forces collisions */

    int vals[20];
    char keys[20][16];
    for (int i = 0; i < 20; i++) {
        vals[i] = i * 10;
        snprintf(keys[i], sizeof(keys[i]), "item_%d", i);
        TEST_ASSERT_EQUAL(0, DscHashmapPut(&map, keys[i], &vals[i]));
    }

    for (int i = 0; i < 20; i++) {
        int *got = (int *)DscHashmapGet(&map, keys[i]);
        TEST_ASSERT_NOT_NULL(got);
        TEST_ASSERT_EQUAL(i * 10, *got);
    }

    DscHashmapFree(&map);
}

void hashmap_clear(void)
{
    DscHashmap map;
    DscHashmapInit(&map, 16);

    int a = 1, b = 2;
    DscHashmapPut(&map, "a", &a);
    DscHashmapPut(&map, "b", &b);
    DscHashmapClear(&map);

    TEST_ASSERT_EQUAL_size_t(0, DscHashmapCount(&map));
    TEST_ASSERT_NULL(DscHashmapGet(&map, "a"));
    TEST_ASSERT_NULL(DscHashmapGet(&map, "b"));

    DscHashmapFree(&map);
}

/* ================================================================== */
/* Strbuf tests                                                       */
/* ================================================================== */

void strbuf_append(void)
{
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);

    DscStrbufAppend(&sb, "hello");
    DscStrbufAppend(&sb, " world");
    TEST_ASSERT_EQUAL_STRING("hello world", DscStrbufCstr(&sb));
    TEST_ASSERT_EQUAL_size_t(11, sb.len);

    DscStrbufFree(&sb);
}

void strbuf_appendf(void)
{
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);

    DscStrbufAppendf(&sb, "val=%d hex=0x%X", 42, 255);
    TEST_ASSERT_EQUAL_STRING("val=42 hex=0xFF", DscStrbufCstr(&sb));

    DscStrbufFree(&sb);
}

void strbuf_indent(void)
{
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);

    DscStrbufIndent(&sb, 3);  /* 3 * 2 = 6 spaces */
    DscStrbufAppend(&sb, "x");
    TEST_ASSERT_EQUAL_STRING("      x", DscStrbufCstr(&sb));

    DscStrbufFree(&sb);
}

void strbuf_reset_keeps_capacity(void)
{
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);

    DscStrbufAppend(&sb, "some data");
    UINT32 cap_before = sb.cap;

    DscStrbufReset(&sb);
    TEST_ASSERT_EQUAL_size_t(0, sb.len);
    TEST_ASSERT_EQUAL_STRING("", DscStrbufCstr(&sb));
    TEST_ASSERT_EQUAL_size_t(cap_before, sb.cap);

    DscStrbufFree(&sb);
}

void strbuf_appendn(void)
{
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);

    DscStrbufAppendn(&sb, "hello world", 5);
    TEST_ASSERT_EQUAL_STRING("hello", DscStrbufCstr(&sb));
    TEST_ASSERT_EQUAL_size_t(5, sb.len);

    DscStrbufFree(&sb);
}

void strbuf_grows_on_large_append(void)
{
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);

    /* Append more than initial capacity */
    for (int i = 0; i < 200; i++) {
        DscStrbufAppend(&sb, "x");
    }
    TEST_ASSERT_EQUAL_size_t(200, sb.len);
    /* Verify all chars are 'x' */
    const char *s = DscStrbufCstr(&sb);
    TEST_ASSERT_EQUAL('x', s[0]);
    TEST_ASSERT_EQUAL('x', s[199]);
    TEST_ASSERT_EQUAL('\0', s[200]);

    DscStrbufFree(&sb);
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
