/* PURPOSE: Minimal assert-based test framework — no external dependencies
 * PATTERN: Macro-based test runner with pass/fail tracking
 * FOR: All test files in this directory include this header */

#ifndef TEST_HELPER_H
#define TEST_HELPER_H

#include <stdio.h>
#include <string.h>

static int _test_count = 0;
static int _test_pass = 0;
static int _test_fail = 0;

#define TEST(name) static void name(void)
#define RUN_TEST(name) do { \
    _test_count++; \
    printf("  %-50s ", #name); \
    name(); \
    _test_pass++; \
    printf("PASS\n"); \
} while(0)

#define ASSERT(expr) do { \
    if (!(expr)) { \
        _test_fail++; _test_pass--; \
        printf("FAIL\n    %s:%d: %s\n", __FILE__, __LINE__, #expr); \
        return; \
    } \
} while(0)

#define ASSERT_EQ(a, b) ASSERT((a) == (b))
#define ASSERT_NE(a, b) ASSERT((a) != (b))
#define ASSERT_STR_EQ(a, b) ASSERT(strcmp((a), (b)) == 0)
#define ASSERT_NULL(a) ASSERT((a) == NULL)
#define ASSERT_NOT_NULL(a) ASSERT((a) != NULL)

#define TEST_SUMMARY() do { \
    printf("\n%d tests, %d passed, %d failed\n", \
           _test_count, _test_pass, _test_fail); \
    return _test_fail > 0 ? 1 : 0; \
} while(0)

#endif /* TEST_HELPER_H */
