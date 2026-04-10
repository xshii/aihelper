/* PURPOSE: Full pipeline integration test — resolve -> read -> format */

#include "test_helper.h"
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

TEST(pipeline_resolve_read_format_field)
{
    setup_all();

    dsc_arch_t *arch = mock_arch_identity();
    dsc_transport_t *tp = mock_transport_create();

    /* Plant data: at address 0x100, struct {x=42, y=99} */
    uint32_t x_val = 42;
    uint32_t y_val = 99;
    mock_transport_set_memory(tp, 0x100, &x_val, 4);
    mock_transport_set_memory(tp, 0x104, &y_val, 4);

    /* Step 1: resolve "g_point.y" */
    dsc_resolved_t resolved;
    int rc = dsc_resolve(&s_symtab, arch, "g_point.y", &resolved);
    ASSERT_EQ(rc, DSC_OK);
    ASSERT_EQ(resolved.addr, (uint64_t)0x104);
    ASSERT_EQ(resolved.size, (size_t)4);

    /* Step 2: read memory */
    uint8_t read_buf[4];
    rc = dsc_mem_read(tp, arch, resolved.addr, read_buf, resolved.size);
    ASSERT_EQ(rc, DSC_OK);

    /* Step 3: format */
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 64);
    rc = dsc_format(read_buf, resolved.size, resolved.type, NULL, &sb);
    ASSERT_EQ(rc, DSC_OK);
    ASSERT_STR_EQ(dsc_strbuf_cstr(&sb), "99");

    dsc_strbuf_free(&sb);
    mock_transport_destroy(tp);
    teardown_all();
}

/* ================================================================== */
/* Test: full struct read and format                                  */
/* ================================================================== */

TEST(pipeline_full_struct_format)
{
    setup_all();

    dsc_arch_t *arch = mock_arch_identity();
    dsc_transport_t *tp = mock_transport_create();

    uint32_t x_val = 10;
    uint32_t y_val = 20;
    mock_transport_set_memory(tp, 0x100, &x_val, 4);
    mock_transport_set_memory(tp, 0x104, &y_val, 4);

    /* Resolve the struct itself */
    dsc_resolved_t resolved;
    int rc = dsc_resolve(&s_symtab, arch, "g_point", &resolved);
    ASSERT_EQ(rc, DSC_OK);
    ASSERT_EQ(resolved.size, (size_t)8);

    /* Read full struct */
    uint8_t buf[8];
    rc = dsc_mem_read(tp, arch, resolved.addr, buf, resolved.size);
    ASSERT_EQ(rc, DSC_OK);

    /* Format */
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 256);
    rc = dsc_format(buf, resolved.size, resolved.type, NULL, &sb);
    ASSERT_EQ(rc, DSC_OK);

    const char *result = dsc_strbuf_cstr(&sb);
    ASSERT(strstr(result, ".x = 10") != NULL);
    ASSERT(strstr(result, ".y = 20") != NULL);

    dsc_strbuf_free(&sb);
    mock_transport_destroy(tp);
    teardown_all();
}

/* ================================================================== */
/* Test: transport records read calls                                 */
/* ================================================================== */

TEST(pipeline_transport_records_calls)
{
    setup_all();

    dsc_arch_t *arch = mock_arch_identity();
    dsc_transport_t *tp = mock_transport_create();

    uint32_t val = 0;
    mock_transport_set_memory(tp, 0x100, &val, 4);

    uint8_t buf[4];
    dsc_mem_read(tp, arch, 0x100, buf, 4);

    const mock_transport_record_t *rec = mock_transport_get_record(tp);
    ASSERT(rec->call_count >= 1);
    ASSERT_EQ(rec->last_addr, (uint64_t)0x100);
    ASSERT_EQ(rec->last_len, (size_t)4);

    mock_transport_destroy(tp);
    teardown_all();
}

/* ================================================================== */
/* Runner                                                             */
/* ================================================================== */

int test_integration_main(void)
{
    printf("=== test_integration ===\n");

    RUN_TEST(pipeline_resolve_read_format_field);
    RUN_TEST(pipeline_full_struct_format);
    RUN_TEST(pipeline_transport_records_calls);

    TEST_SUMMARY();
}
