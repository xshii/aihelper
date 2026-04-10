/* PURPOSE: Full pipeline integration test — resolve -> read -> format */

#include "unity/unity.h"
#include "mocks/mock_transport.h"
#include "mocks/mock_arch.h"
#include "../src/resolve/resolve.h"
#include "../src/memory/memory.h"
#include "../src/format/format.h"
#include "../src/dwarf/dwarf_types.h"
#include "../src/dwarf/dwarf_symbols.h"
#include "../src/util/strbuf.h"
#include "../src/core/dsc_errors.h"

#include <stdlib.h>
#include <string.h>
#include <stdint.h>


/* ================================================================== */
/* Helpers: static types shared by integration tests                  */
/* ================================================================== */

static dsc_type_t s_uint32_type;
static dsc_type_t s_struct_type;
static dsc_struct_field_t s_fields[2];
static dsc_symtab_t s_symtab;

static void init_uint32(void)
{
    memset(&s_uint32_type, 0, sizeof(s_uint32_type));
    s_uint32_type.kind = DSC_TYPE_BASE;
    s_uint32_type.byte_size = 4;
    s_uint32_type.u.base.encoding = DSC_ENC_UNSIGNED;
}

static void init_struct(void)
{
    memset(&s_struct_type, 0, sizeof(s_struct_type));
    memset(s_fields, 0, sizeof(s_fields));

    s_fields[0].name = "x";
    s_fields[0].byte_offset = 0;
    s_fields[0].type = &s_uint32_type;

    s_fields[1].name = "y";
    s_fields[1].byte_offset = 4;
    s_fields[1].type = &s_uint32_type;

    s_struct_type.kind = DSC_TYPE_STRUCT;
    s_struct_type.byte_size = 8;
    s_struct_type.u.composite.fields = s_fields;
    s_struct_type.u.composite.field_count = 2;
}

static void setup_all(void)
{
    init_uint32();
    init_struct();
    dsc_symtab_init(&s_symtab);
    dsc_symtab_add(&s_symtab, "g_point", 0x100, 8,
                   &s_struct_type, 1);
}

static void teardown_all(void)
{
    dsc_symtab_free(&s_symtab);
}

/* ================================================================== */
/* Test: resolve -> read -> format a struct field                     */
/* ================================================================== */

void pipeline_resolve_read_format_field(void)
{
    setup_all();

    DscArch *arch = mock_arch_identity();
    DscTransport *tp = mock_transport_create();

    /* Plant data: at address 0x100, struct {x=42, y=99} */
    UINT32 x_val = 42;
    UINT32 y_val = 99;
    mock_transport_set_memory(tp, 0x100, &x_val, 4);
    mock_transport_set_memory(tp, 0x104, &y_val, 4);

    /* Step 1: resolve "g_point.y" */
    DscResolved resolved;
    int rc = DscResolve(&s_symtab, arch, "g_point.y", &resolved);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_UINT64(0x104, resolved.addr);
    TEST_ASSERT_EQUAL_size_t(4, resolved.size);

    /* Step 2: read memory */
    UINT8 read_buf[4];
    rc = DscMemRead(tp, arch, resolved.addr, read_buf, resolved.size);
    TEST_ASSERT_EQUAL(DSC_OK, rc);

    /* Step 3: format */
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);
    rc = DscFormat(read_buf, resolved.size, resolved.type, NULL, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_STRING("99", DscStrbufCstr(&sb));

    DscStrbufFree(&sb);
    mock_transport_destroy(tp);
    teardown_all();
}

/* ================================================================== */
/* Test: full struct read and format                                  */
/* ================================================================== */

void pipeline_full_struct_format(void)
{
    setup_all();

    DscArch *arch = mock_arch_identity();
    DscTransport *tp = mock_transport_create();

    UINT32 x_val = 10;
    UINT32 y_val = 20;
    mock_transport_set_memory(tp, 0x100, &x_val, 4);
    mock_transport_set_memory(tp, 0x104, &y_val, 4);

    /* Resolve the struct itself */
    DscResolved resolved;
    int rc = DscResolve(&s_symtab, arch, "g_point", &resolved);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_size_t(8, resolved.size);

    /* Read full struct */
    UINT8 buf[8];
    rc = DscMemRead(tp, arch, resolved.addr, buf, resolved.size);
    TEST_ASSERT_EQUAL(DSC_OK, rc);

    /* Format */
    DscStrbuf sb;
    DscStrbufInit(&sb, 256);
    rc = DscFormat(buf, resolved.size, resolved.type, NULL, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);

    const char *result = DscStrbufCstr(&sb);
    TEST_ASSERT_TRUE(strstr(result, ".x = 10") != NULL);
    TEST_ASSERT_TRUE(strstr(result, ".y = 20") != NULL);

    DscStrbufFree(&sb);
    mock_transport_destroy(tp);
    teardown_all();
}

/* ================================================================== */
/* Test: transport records read calls                                 */
/* ================================================================== */

void pipeline_transport_records_calls(void)
{
    setup_all();

    DscArch *arch = mock_arch_identity();
    DscTransport *tp = mock_transport_create();

    UINT32 val = 0;
    mock_transport_set_memory(tp, 0x100, &val, 4);

    UINT8 buf[4];
    DscMemRead(tp, arch, 0x100, buf, 4);

    const mock_transport_record_t *rec = mock_transport_get_record(tp);
    TEST_ASSERT_TRUE(rec->call_count >= 1);
    TEST_ASSERT_EQUAL_UINT64(0x100, rec->last_addr);
    TEST_ASSERT_EQUAL_size_t(4, rec->last_len);

    mock_transport_destroy(tp);
    teardown_all();
}

/* ================================================================== */
/* Runner                                                             */
/* ================================================================== */

int test_integration_main(void)
{
    UNITY_BEGIN();

    RUN_TEST(pipeline_resolve_read_format_field);
    RUN_TEST(pipeline_full_struct_format);
    RUN_TEST(pipeline_transport_records_calls);

    return UNITY_END();
}
