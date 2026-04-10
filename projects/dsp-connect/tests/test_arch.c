/* PURPOSE: Tests for arch adapters — byte_le identity and word16 translation */

#include "test_helper.h"
#include "mocks/mock_arch.h"
#include "../src/arch/arch.h"
#include "../src/core/dsc_errors.h"

/* ================================================================== */
/* Identity arch (byte_le) tests                                      */
/* ================================================================== */

TEST(identity_logical_equals_physical)
{
    dsc_arch_t *a = mock_arch_identity();
    uint64_t phys = 0;

    int rc = dsc_arch_logical_to_physical(a, 0x1000, &phys);
    ASSERT_EQ(rc, DSC_OK);
    ASSERT_EQ(phys, (uint64_t)0x1000);
}

TEST(identity_physical_equals_logical)
{
    dsc_arch_t *a = mock_arch_identity();
    uint64_t logical = 0;

    int rc = dsc_arch_physical_to_logical(a, 0x2000, &logical);
    ASSERT_EQ(rc, DSC_OK);
    ASSERT_EQ(logical, (uint64_t)0x2000);
}

TEST(identity_no_endian_swap)
{
    dsc_arch_t *a = mock_arch_identity();
    uint8_t buf[] = {0x01, 0x02, 0x03, 0x04};

    dsc_arch_swap_endian(a, buf, 4);
    /* Identity: no swap, bytes unchanged */
    ASSERT_EQ(buf[0], 0x01);
    ASSERT_EQ(buf[1], 0x02);
    ASSERT_EQ(buf[2], 0x03);
    ASSERT_EQ(buf[3], 0x04);
}

TEST(identity_min_access_is_one)
{
    dsc_arch_t *a = mock_arch_identity();
    ASSERT_EQ(dsc_arch_min_access_size(a), (size_t)1);
}

TEST(identity_word_size_is_one)
{
    dsc_arch_t *a = mock_arch_identity();
    ASSERT_EQ(dsc_arch_word_size(a), (size_t)1);
}

/* ================================================================== */
/* Word16 arch tests                                                  */
/* ================================================================== */

TEST(word16_logical_to_physical_divides_by_two)
{
    dsc_arch_t *a = mock_arch_word16();
    uint64_t phys = 0;

    int rc = dsc_arch_logical_to_physical(a, 0x100, &phys);
    ASSERT_EQ(rc, DSC_OK);
    ASSERT_EQ(phys, (uint64_t)0x80);
}

TEST(word16_physical_to_logical_multiplies_by_two)
{
    dsc_arch_t *a = mock_arch_word16();
    uint64_t logical = 0;

    int rc = dsc_arch_physical_to_logical(a, 0x80, &logical);
    ASSERT_EQ(rc, DSC_OK);
    ASSERT_EQ(logical, (uint64_t)0x100);
}

TEST(word16_unaligned_returns_error)
{
    dsc_arch_t *a = mock_arch_word16();
    uint64_t phys = 0;

    int rc = dsc_arch_logical_to_physical(a, 0x101, &phys);
    ASSERT_EQ(rc, DSC_ERR_MEM_ALIGN);
}

TEST(word16_zero_address)
{
    dsc_arch_t *a = mock_arch_word16();
    uint64_t phys = 0;

    int rc = dsc_arch_logical_to_physical(a, 0, &phys);
    ASSERT_EQ(rc, DSC_OK);
    ASSERT_EQ(phys, (uint64_t)0);
}

TEST(word16_min_access_is_two)
{
    dsc_arch_t *a = mock_arch_word16();
    ASSERT_EQ(dsc_arch_min_access_size(a), (size_t)2);
}

TEST(word16_word_size_is_two)
{
    dsc_arch_t *a = mock_arch_word16();
    ASSERT_EQ(dsc_arch_word_size(a), (size_t)2);
}

/* ================================================================== */
/* Runner                                                             */
/* ================================================================== */

int test_arch_main(void)
{
    printf("=== test_arch ===\n");

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

    TEST_SUMMARY();
}
