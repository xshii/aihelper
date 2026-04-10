/* PURPOSE: Tests for error code to string mapping */

#include "unity/unity.h"
#include "../src/core/dsc_errors.h"

#include <string.h>


/* ================================================================== */
/* Tests                                                              */
/* ================================================================== */

void strerror_ok(void)
{
    TEST_ASSERT_EQUAL_STRING("success", DscStrerror(DSC_OK));
}

void strerror_not_found(void)
{
    TEST_ASSERT_EQUAL_STRING("symbol not found",
                             DscStrerror(DSC_ERR_NOT_FOUND));
}

void strerror_nomem(void)
{
    TEST_ASSERT_EQUAL_STRING("out of memory",
                             DscStrerror(DSC_ERR_NOMEM));
}

void strerror_invalid_arg(void)
{
    TEST_ASSERT_EQUAL_STRING("invalid argument",
                             DscStrerror(DSC_ERR_INVALID_ARG));
}

void strerror_transport_open(void)
{
    TEST_ASSERT_EQUAL_STRING("transport connection failed",
                             DscStrerror(DSC_ERR_TRANSPORT_OPEN));
}

void strerror_transport_io(void)
{
    TEST_ASSERT_EQUAL_STRING("transport I/O error",
                             DscStrerror(DSC_ERR_TRANSPORT_IO));
}

void strerror_mem_align(void)
{
    TEST_ASSERT_EQUAL_STRING("unaligned memory access",
                             DscStrerror(DSC_ERR_MEM_ALIGN));
}

void strerror_unknown_code(void)
{
    TEST_ASSERT_EQUAL_STRING("unknown error", DscStrerror(9999));
}

void strerror_negative_unknown(void)
{
    TEST_ASSERT_EQUAL_STRING("unknown error", DscStrerror(-9999));
}

/* ================================================================== */
/* Runner                                                             */
/* ================================================================== */

int test_errors_main(void)
{
    UNITY_BEGIN();

    RUN_TEST(strerror_ok);
    RUN_TEST(strerror_not_found);
    RUN_TEST(strerror_nomem);
    RUN_TEST(strerror_invalid_arg);
    RUN_TEST(strerror_transport_open);
    RUN_TEST(strerror_transport_io);
    RUN_TEST(strerror_mem_align);
    RUN_TEST(strerror_unknown_code);
    RUN_TEST(strerror_negative_unknown);

    return UNITY_END();
}
