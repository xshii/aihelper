/* PURPOSE: Tests for arch adapters — byte_le identity and word16 translation */

#include "unity/unity.h"
#include "mocks/mock_arch.h"
#include "../src/arch/arch.h"
#include "../src/core/dsc_errors.h"


/* ================================================================== */
/* Identity arch (byte_le) tests                                      */
/* ================================================================== */

void identity_logical_equals_physical(void)
{
    dsc_arch_t *a = mock_arch_identity();
    UINT64 phys = 0;

    int rc = dsc_arch_logical_to_physical(a, 0x1000, &phys);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_UINT64(0x1000, phys);
}

void identity_physical_equals_logical(void)
{
    dsc_arch_t *a = mock_arch_identity();
    UINT64 logical = 0;

    int rc = dsc_arch_physical_to_logical(a, 0x2000, &logical);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_UINT64(0x2000, logical);
}

void identity_no_endian_swap(void)
{
    dsc_arch_t *a = mock_arch_identity();
    UINT8 buf[] = {0x01, 0x02, 0x03, 0x04};

    dsc_arch_swap_endian(a, buf, 4);
    /* Identity: no swap, bytes unchanged */
    TEST_ASSERT_EQUAL(0x01, buf[0]);
    TEST_ASSERT_EQUAL(0x02, buf[1]);
    TEST_ASSERT_EQUAL(0x03, buf[2]);
    TEST_ASSERT_EQUAL(0x04, buf[3]);
}

void identity_min_access_is_one(void)
{
    dsc_arch_t *a = mock_arch_identity();
    TEST_ASSERT_EQUAL_size_t(1, dsc_arch_min_access_size(a));
}

void identity_word_size_is_one(void)
{
    dsc_arch_t *a = mock_arch_identity();
    TEST_ASSERT_EQUAL_size_t(1, dsc_arch_word_size(a));
}

/* ================================================================== */
/* Word16 arch tests                                                  */
/* ================================================================== */

void word16_logical_to_physical_divides_by_two(void)
{
    dsc_arch_t *a = mock_arch_word16();
    UINT64 phys = 0;

    int rc = dsc_arch_logical_to_physical(a, 0x100, &phys);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_UINT64(0x80, phys);
}

void word16_physical_to_logical_multiplies_by_two(void)
{
    dsc_arch_t *a = mock_arch_word16();
    UINT64 logical = 0;

    int rc = dsc_arch_physical_to_logical(a, 0x80, &logical);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_UINT64(0x100, logical);
}

void word16_unaligned_returns_error(void)
{
    dsc_arch_t *a = mock_arch_word16();
    UINT64 phys = 0;

    int rc = dsc_arch_logical_to_physical(a, 0x101, &phys);
    TEST_ASSERT_EQUAL(DSC_ERR_MEM_ALIGN, rc);
}

void word16_zero_address(void)
{
    dsc_arch_t *a = mock_arch_word16();
    UINT64 phys = 0;

    int rc = dsc_arch_logical_to_physical(a, 0, &phys);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_UINT64(0, phys);
}

void word16_min_access_is_two(void)
{
    dsc_arch_t *a = mock_arch_word16();
    TEST_ASSERT_EQUAL_size_t(2, dsc_arch_min_access_size(a));
}

void word16_word_size_is_two(void)
{
    dsc_arch_t *a = mock_arch_word16();
    TEST_ASSERT_EQUAL_size_t(2, dsc_arch_word_size(a));
}

/* ================================================================== */
/* Runner                                                             */
/* ================================================================== */

int test_arch_main(void)
{
    UNITY_BEGIN();

    RUN_TEST(identity_logical_equals_physical);
    RUN_TEST(identity_physical_equals_logical);
    RUN_TEST(identity_no_endian_swap);
    RUN_TEST(identity_min_access_is_one);
    RUN_TEST(identity_word_size_is_one);

    RUN_TEST(word16_logical_to_physical_divides_by_two);
    RUN_TEST(word16_physical_to_logical_multiplies_by_two);
    RUN_TEST(word16_unaligned_returns_error);
    RUN_TEST(word16_zero_address);
    RUN_TEST(word16_min_access_is_two);
    RUN_TEST(word16_word_size_is_two);

    return UNITY_END();
}
