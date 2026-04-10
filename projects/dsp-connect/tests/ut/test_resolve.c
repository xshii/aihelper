/* PURPOSE: Tests for symbol path resolution */

#include "unity/unity.h"
#include "mocks/mock_arch.h"
#include "../src/resolve/resolve.h"
#include "../src/dwarf/dwarf_types.h"
#include "../src/dwarf/dwarf_symbols.h"
#include "../src/core/dsc_errors.h"

#include <stdlib.h>
#include <string.h>


/* ================================================================== */
/* Helpers: build mock type objects on the stack/heap                  */
/* ================================================================== */

/* Build a uint32 base type (static, no heap) */
static dsc_type_t s_uint32_type;

static void init_uint32_type(void)
{
    memset(&s_uint32_type, 0, sizeof(s_uint32_type));
    s_uint32_type.kind = DSC_TYPE_BASE;
    s_uint32_type.name = NULL;  /* Not heap-allocated */
    s_uint32_type.byte_size = 4;
    s_uint32_type.u.base.encoding = DSC_ENC_UNSIGNED;
}

/* Build a struct type with two fields: "x" (uint32 at +0) and "y" (uint32 at +4) */
static dsc_type_t s_struct_type;
static dsc_struct_field_t s_struct_fields[2];

static void init_struct_type(void)
{
    memset(&s_struct_type, 0, sizeof(s_struct_type));
    memset(s_struct_fields, 0, sizeof(s_struct_fields));

    s_struct_fields[0].name = "x";
    s_struct_fields[0].byte_offset = 0;
    s_struct_fields[0].type = &s_uint32_type;

    s_struct_fields[1].name = "y";
    s_struct_fields[1].byte_offset = 4;
    s_struct_fields[1].type = &s_uint32_type;

    s_struct_type.kind = DSC_TYPE_STRUCT;
    s_struct_type.name = NULL;
    s_struct_type.byte_size = 8;
    s_struct_type.u.composite.fields = s_struct_fields;
    s_struct_type.u.composite.field_count = 2;
}

/* Build an array type: uint32[4] */
static dsc_type_t s_array_type;
static dsc_array_dim_t s_array_dim;

static void init_array_type(void)
{
    memset(&s_array_type, 0, sizeof(s_array_type));
    memset(&s_array_dim, 0, sizeof(s_array_dim));

    s_array_dim.lower_bound = 0;
    s_array_dim.count = 4;

    s_array_type.kind = DSC_TYPE_ARRAY;
    s_array_type.name = NULL;
    s_array_type.byte_size = 16;  /* 4 * sizeof(uint32) */
    s_array_type.u.array.element_type = &s_uint32_type;
    s_array_type.u.array.dims = &s_array_dim;
    s_array_type.u.array.dim_count = 1;
}

/* Shared symtab setup */
static dsc_symtab_t s_symtab;

static void setup_symtab(void)
{
    init_uint32_type();
    init_struct_type();
    init_array_type();

    dsc_symtab_init(&s_symtab);
    dsc_symtab_add(&s_symtab, "simple_var", 0x1000, 4,
                   &s_uint32_type, 1);
    dsc_symtab_add(&s_symtab, "my_struct", 0x2000, 8,
                   &s_struct_type, 1);
    dsc_symtab_add(&s_symtab, "arr", 0x3000, 16,
                   &s_array_type, 1);
}

static void teardown_symtab(void)
{
    dsc_symtab_free(&s_symtab);
}

/* ================================================================== */
/* Tests                                                              */
/* ================================================================== */

void resolve_simple_variable(void)
{
    setup_symtab();
    dsc_arch_t *arch = mock_arch_identity();
    dsc_resolved_t out;

    int rc = dsc_resolve(&s_symtab, arch, "simple_var", &out);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_UINT64(0x1000, out.addr);
    TEST_ASSERT_EQUAL_size_t(4, out.size);
    TEST_ASSERT_EQUAL_PTR(&s_uint32_type, out.type);

    teardown_symtab();
}

void resolve_struct_field(void)
{
    setup_symtab();
    dsc_arch_t *arch = mock_arch_identity();
    dsc_resolved_t out;

    int rc = dsc_resolve(&s_symtab, arch, "my_struct.y", &out);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_UINT64(0x2004, out.addr);
    TEST_ASSERT_EQUAL_size_t(4, out.size);

    teardown_symtab();
}

void resolve_array_index(void)
{
    setup_symtab();
    dsc_arch_t *arch = mock_arch_identity();
    dsc_resolved_t out;

    int rc = dsc_resolve(&s_symtab, arch, "arr[2]", &out);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_UINT64(0x3008, out.addr);  /* 0x3000 + 2*4 */
    TEST_ASSERT_EQUAL_size_t(4, out.size);

    teardown_symtab();
}

void resolve_nonexistent_returns_not_found(void)
{
    setup_symtab();
    dsc_arch_t *arch = mock_arch_identity();
    dsc_resolved_t out;

    int rc = dsc_resolve(&s_symtab, arch, "nonexistent", &out);
    TEST_ASSERT_EQUAL(DSC_ERR_NOT_FOUND, rc);

    teardown_symtab();
}

void resolve_empty_path_returns_error(void)
{
    setup_symtab();
    dsc_arch_t *arch = mock_arch_identity();
    dsc_resolved_t out;

    int rc = dsc_resolve(&s_symtab, arch, "", &out);
    TEST_ASSERT_EQUAL(DSC_ERR_INVALID_ARG, rc);

    teardown_symtab();
}

void resolve_null_args_return_error(void)
{
    dsc_resolved_t out;
    int rc = dsc_resolve(NULL, NULL, "x", &out);
    TEST_ASSERT_EQUAL(DSC_ERR_INVALID_ARG, rc);

    rc = dsc_resolve(&s_symtab, NULL, NULL, &out);
    TEST_ASSERT_EQUAL(DSC_ERR_INVALID_ARG, rc);
}

void resolve_array_out_of_bounds(void)
{
    setup_symtab();
    dsc_arch_t *arch = mock_arch_identity();
    dsc_resolved_t out;

    int rc = dsc_resolve(&s_symtab, arch, "arr[99]", &out);
    TEST_ASSERT_EQUAL(DSC_ERR_RESOLVE_INDEX, rc);

    teardown_symtab();
}

void resolve_field_on_non_struct_fails(void)
{
    setup_symtab();
    dsc_arch_t *arch = mock_arch_identity();
    dsc_resolved_t out;

    /* simple_var is uint32, not a struct */
    int rc = dsc_resolve(&s_symtab, arch, "simple_var.field", &out);
    TEST_ASSERT_EQUAL(DSC_ERR_RESOLVE_PATH, rc);

    teardown_symtab();
}

/* ================================================================== */
/* Runner                                                             */
/* ================================================================== */

int test_resolve_main(void)
{
    UNITY_BEGIN();

    RUN_TEST(resolve_simple_variable);
    RUN_TEST(resolve_struct_field);
    RUN_TEST(resolve_array_index);
    RUN_TEST(resolve_nonexistent_returns_not_found);
    RUN_TEST(resolve_empty_path_returns_error);
    RUN_TEST(resolve_null_args_return_error);
    RUN_TEST(resolve_array_out_of_bounds);
    RUN_TEST(resolve_field_on_non_struct_fails);

    return UNITY_END();
}
