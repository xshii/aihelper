/* PURPOSE: Tests for type-aware formatting */

#include "unity/unity.h"
#include "../src/format/format.h"
#include "../src/dwarf/dwarf_types.h"
#include "../src/util/strbuf.h"
#include "../src/core/dsc_errors.h"

#include <stdlib.h>
#include <string.h>
#include <stdint.h>


/* ================================================================== */
/* Helpers: build type objects                                        */
/* ================================================================== */

static dsc_type_t *make_uint32_type(void)
{
    dsc_type_t *t = calloc(1, sizeof(*t));
    t->kind = DSC_TYPE_BASE;
    t->byte_size = 4;
    t->u.base.encoding = DSC_ENC_UNSIGNED;
    return t;
}

static dsc_type_t *make_int16_type(void)
{
    dsc_type_t *t = calloc(1, sizeof(*t));
    t->kind = DSC_TYPE_BASE;
    t->byte_size = 2;
    t->u.base.encoding = DSC_ENC_SIGNED;
    return t;
}

/* Build an enum with STATE_IDLE=0, STATE_RUN=1, STATE_ERR=2 */
static dsc_enum_value_t s_enum_vals[3];

static dsc_type_t *make_state_enum_type(void)
{
    s_enum_vals[0].name = "STATE_IDLE";
    s_enum_vals[0].value = 0;
    s_enum_vals[1].name = "STATE_RUN";
    s_enum_vals[1].value = 1;
    s_enum_vals[2].name = "STATE_ERR";
    s_enum_vals[2].value = 2;

    dsc_type_t *t = calloc(1, sizeof(*t));
    t->kind = DSC_TYPE_ENUM;
    t->byte_size = 4;
    t->u.enumeration.values = s_enum_vals;
    t->u.enumeration.value_count = 3;
    t->u.enumeration.underlying = NULL;
    return t;
}

/* Build a struct type with "a" (uint32 at +0) and "b" (uint32 at +4) */
static dsc_type_t s_field_uint32;
static dsc_struct_field_t s_struct_fields[2];

static dsc_type_t *make_struct_type(void)
{
    memset(&s_field_uint32, 0, sizeof(s_field_uint32));
    s_field_uint32.kind = DSC_TYPE_BASE;
    s_field_uint32.byte_size = 4;
    s_field_uint32.u.base.encoding = DSC_ENC_UNSIGNED;

    s_struct_fields[0].name = "a";
    s_struct_fields[0].byte_offset = 0;
    s_struct_fields[0].type = &s_field_uint32;

    s_struct_fields[1].name = "b";
    s_struct_fields[1].byte_offset = 4;
    s_struct_fields[1].type = &s_field_uint32;

    dsc_type_t *t = calloc(1, sizeof(*t));
    t->kind = DSC_TYPE_STRUCT;
    t->byte_size = 8;
    t->u.composite.fields = s_struct_fields;
    t->u.composite.field_count = 2;
    return t;
}

/* Build array type: uint32[3] */
static dsc_type_t s_elem_uint32;
static dsc_array_dim_t s_arr_dim;

static dsc_type_t *make_uint32_array_type(void)
{
    memset(&s_elem_uint32, 0, sizeof(s_elem_uint32));
    s_elem_uint32.kind = DSC_TYPE_BASE;
    s_elem_uint32.byte_size = 4;
    s_elem_uint32.u.base.encoding = DSC_ENC_UNSIGNED;

    s_arr_dim.lower_bound = 0;
    s_arr_dim.count = 3;

    dsc_type_t *t = calloc(1, sizeof(*t));
    t->kind = DSC_TYPE_ARRAY;
    t->byte_size = 12;
    t->u.array.element_type = &s_elem_uint32;
    t->u.array.dims = &s_arr_dim;
    t->u.array.dim_count = 1;
    return t;
}

/* ================================================================== */
/* Format uint32 test                                                 */
/* ================================================================== */

void format_uint32_decimal(void)
{
    dsc_type_t *type = make_uint32_type();
    UINT32 val = 42;
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 64);

    dsc_format_opts_t opts = dsc_format_opts_default();
    int rc = dsc_format(&val, sizeof(val), type, &opts, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_STRING("42", dsc_strbuf_cstr(&sb));

    dsc_strbuf_free(&sb);
    free(type);
}

void format_uint32_hex(void)
{
    dsc_type_t *type = make_uint32_type();
    UINT32 val = 42;
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 64);

    dsc_format_opts_t opts = dsc_format_opts_default();
    opts.hex_integers = 1;
    int rc = dsc_format(&val, sizeof(val), type, &opts, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_STRING("0x0000002A", dsc_strbuf_cstr(&sb));

    dsc_strbuf_free(&sb);
    free(type);
}

void format_int16_negative(void)
{
    dsc_type_t *type = make_int16_type();
    INT16 val = -100;
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 64);

    dsc_format_opts_t opts = dsc_format_opts_default();
    int rc = dsc_format(&val, sizeof(val), type, &opts, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_STRING("-100", dsc_strbuf_cstr(&sb));

    dsc_strbuf_free(&sb);
    free(type);
}

/* ================================================================== */
/* Format enum test                                                   */
/* ================================================================== */

void format_enum_known_value(void)
{
    dsc_type_t *type = make_state_enum_type();
    INT32 val = 0;  /* STATE_IDLE */
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 64);

    dsc_format_opts_t opts = dsc_format_opts_default();
    int rc = dsc_format(&val, sizeof(val), type, &opts, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_STRING("STATE_IDLE (0)", dsc_strbuf_cstr(&sb));

    dsc_strbuf_free(&sb);
    free(type);
}

void format_enum_second_value(void)
{
    dsc_type_t *type = make_state_enum_type();
    INT32 val = 1;  /* STATE_RUN */
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 64);

    dsc_format_opts_t opts = dsc_format_opts_default();
    int rc = dsc_format(&val, sizeof(val), type, &opts, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_STRING("STATE_RUN (1)", dsc_strbuf_cstr(&sb));

    dsc_strbuf_free(&sb);
    free(type);
}

/* ================================================================== */
/* Format struct test                                                 */
/* ================================================================== */

void format_struct_multiline(void)
{
    dsc_type_t *type = make_struct_type();

    /* data: a=10, b=20 */
    UINT8 data[8];
    UINT32 a_val = 10, b_val = 20;
    memcpy(data + 0, &a_val, 4);
    memcpy(data + 4, &b_val, 4);

    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 256);

    dsc_format_opts_t opts = dsc_format_opts_default();
    int rc = dsc_format(data, sizeof(data), type, &opts, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);

    const char *result = dsc_strbuf_cstr(&sb);
    /* Should contain field names and values */
    TEST_ASSERT_TRUE(strstr(result, ".a = 10") != NULL);
    TEST_ASSERT_TRUE(strstr(result, ".b = 20") != NULL);
    TEST_ASSERT_TRUE(strstr(result, "{") != NULL);
    TEST_ASSERT_TRUE(strstr(result, "}") != NULL);

    dsc_strbuf_free(&sb);
    free(type);
}

/* ================================================================== */
/* Format array test                                                  */
/* ================================================================== */

void format_array_elements(void)
{
    dsc_type_t *type = make_uint32_array_type();

    UINT32 data[3] = {100, 200, 300};
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 256);

    dsc_format_opts_t opts = dsc_format_opts_default();
    int rc = dsc_format(data, sizeof(data), type, &opts, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);

    const char *result = dsc_strbuf_cstr(&sb);
    /* Small array of primitives uses compact display */
    TEST_ASSERT_TRUE(strstr(result, "[0] = 100") != NULL);
    TEST_ASSERT_TRUE(strstr(result, "[1] = 200") != NULL);
    TEST_ASSERT_TRUE(strstr(result, "[2] = 300") != NULL);

    dsc_strbuf_free(&sb);
    free(type);
}

/* ================================================================== */
/* Format with NULL opts uses defaults                                */
/* ================================================================== */

void format_null_opts_uses_defaults(void)
{
    dsc_type_t *type = make_uint32_type();
    UINT32 val = 7;
    dsc_strbuf_t sb;
    dsc_strbuf_init(&sb, 64);

    int rc = dsc_format(&val, sizeof(val), type, NULL, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_STRING("7", dsc_strbuf_cstr(&sb));

    dsc_strbuf_free(&sb);
    free(type);
}

/* ================================================================== */
/* format_str convenience function                                    */
/* ================================================================== */

void format_str_returns_allocated_string(void)
{
    dsc_type_t *type = make_uint32_type();
    UINT32 val = 99;

    char *result = dsc_format_str(&val, sizeof(val), type, NULL);
    TEST_ASSERT_NOT_NULL(result);
    TEST_ASSERT_EQUAL_STRING("99", result);

    free(result);
    free(type);
}

/* ================================================================== */
/* Runner                                                             */
/* ================================================================== */

int test_format_main(void)
{
    UNITY_BEGIN();

    RUN_TEST(format_uint32_decimal);
    RUN_TEST(format_uint32_hex);
    RUN_TEST(format_int16_negative);
    RUN_TEST(format_enum_known_value);
    RUN_TEST(format_enum_second_value);
    RUN_TEST(format_struct_multiline);
    RUN_TEST(format_array_elements);
    RUN_TEST(format_null_opts_uses_defaults);
    RUN_TEST(format_str_returns_allocated_string);

    return UNITY_END();
}
