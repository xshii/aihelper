/* PURPOSE: Tests for error code to string mapping */

#include "test_helper.h"
#include "../src/core/dsc_errors.h"

#include <string.h>

/* ================================================================== */
/* Tests                                                              */
/* ================================================================== */

TEST(strerror_ok)
{
    ASSERT_STR_EQ(dsc_strerror(DSC_OK), "success");
}

TEST(strerror_not_found)
{
    ASSERT_STR_EQ(dsc_strerror(DSC_ERR_NOT_FOUND), "symbol not found");
}

TEST(strerror_nomem)
{
    ASSERT_STR_EQ(dsc_strerror(DSC_ERR_NOMEM), "out of memory");
}

TEST(strerror_invalid_arg)
{
    ASSERT_STR_EQ(dsc_strerror(DSC_ERR_INVALID_ARG), "invalid argument");
}

TEST(strerror_transport_open)
{
    ASSERT_STR_EQ(dsc_strerror(DSC_ERR_TRANSPORT_OPEN),
                  "transport connection failed");
}

TEST(strerror_transport_io)
{
    ASSERT_STR_EQ(dsc_strerror(DSC_ERR_TRANSPORT_IO),
                  "transport I/O error");
}

TEST(strerror_mem_align)
{
    ASSERT_STR_EQ(dsc_strerror(DSC_ERR_MEM_ALIGN),
                  "unaligned memory access");
}

TEST(strerror_unknown_code)
{
    ASSERT_STR_EQ(dsc_strerror(9999), "unknown error");
}

TEST(strerror_negative_unknown)
{
    ASSERT_STR_EQ(dsc_strerror(-9999), "unknown error");
}

/* ================================================================== */
/* Runner                                                             */
/* ================================================================== */

int test_errors_main(void)
{
    printf("=== test_errors ===\n");

    RUN_TEST(strerror_ok);
    RUN_TEST(strerror_not_found);
    RUN_TEST(strerror_nomem);
    RUN_TEST(strerror_invalid_arg);
    RUN_TEST(strerror_transport_open);
    RUN_TEST(strerror_transport_io);
    RUN_TEST(strerror_mem_align);
    RUN_TEST(strerror_unknown_code);
    RUN_TEST(strerror_negative_unknown);

    TEST_SUMMARY();
}
