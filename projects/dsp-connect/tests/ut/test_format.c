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
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);

    DscFormatOpts opts = DscFormatOptsDefault();
    int rc = DscFormat(&val, sizeof(val), type, &opts, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_STRING("42", DscStrbufCstr(&sb));

    DscStrbufFree(&sb);
    free(type);
}

void format_uint32_hex(void)
{
    dsc_type_t *type = make_uint32_type();
    UINT32 val = 42;
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);

    DscFormatOpts opts = DscFormatOptsDefault();
    opts.hex_integers = 1;
    int rc = DscFormat(&val, sizeof(val), type, &opts, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_STRING("0x0000002A", DscStrbufCstr(&sb));

    DscStrbufFree(&sb);
    free(type);
}

void format_int16_negative(void)
{
    dsc_type_t *type = make_int16_type();
    INT16 val = -100;
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);

    DscFormatOpts opts = DscFormatOptsDefault();
    int rc = DscFormat(&val, sizeof(val), type, &opts, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_STRING("-100", DscStrbufCstr(&sb));

    DscStrbufFree(&sb);
    free(type);
}

/* ================================================================== */
/* Format enum test                                                   */
/* ================================================================== */

void format_enum_known_value(void)
{
    dsc_type_t *type = make_state_enum_type();
    INT32 val = 0;  /* STATE_IDLE */
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);

    DscFormatOpts opts = DscFormatOptsDefault();
    int rc = DscFormat(&val, sizeof(val), type, &opts, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_STRING("STATE_IDLE (0)", DscStrbufCstr(&sb));

    DscStrbufFree(&sb);
    free(type);
}

void format_enum_second_value(void)
{
    dsc_type_t *type = make_state_enum_type();
    INT32 val = 1;  /* STATE_RUN */
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);

    DscFormatOpts opts = DscFormatOptsDefault();
    int rc = DscFormat(&val, sizeof(val), type, &opts, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_STRING("STATE_RUN (1)", DscStrbufCstr(&sb));

    DscStrbufFree(&sb);
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

    DscStrbuf sb;
    DscStrbufInit(&sb, 256);

    DscFormatOpts opts = DscFormatOptsDefault();
    int rc = DscFormat(data, sizeof(data), type, &opts, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);

    const char *result = DscStrbufCstr(&sb);
    /* Should contain field names and values */
    TEST_ASSERT_TRUE(strstr(result, ".a = 10") != NULL);
    TEST_ASSERT_TRUE(strstr(result, ".b = 20") != NULL);
    TEST_ASSERT_TRUE(strstr(result, "{") != NULL);
    TEST_ASSERT_TRUE(strstr(result, "}") != NULL);

    DscStrbufFree(&sb);
    free(type);
}

/* ================================================================== */
/* Format array test                                                  */
/* ================================================================== */

void format_array_elements(void)
{
    dsc_type_t *type = make_uint32_array_type();

    UINT32 data[3] = {100, 200, 300};
    DscStrbuf sb;
    DscStrbufInit(&sb, 256);

    DscFormatOpts opts = DscFormatOptsDefault();
    int rc = DscFormat(data, sizeof(data), type, &opts, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);

    const char *result = DscStrbufCstr(&sb);
    /* Small array of primitives uses compact display */
    TEST_ASSERT_TRUE(strstr(result, "[0] = 100") != NULL);
    TEST_ASSERT_TRUE(strstr(result, "[1] = 200") != NULL);
    TEST_ASSERT_TRUE(strstr(result, "[2] = 300") != NULL);

    DscStrbufFree(&sb);
    free(type);
}

/* ================================================================== */
/* Format with NULL opts uses defaults                                */
/* ================================================================== */

void format_null_opts_uses_defaults(void)
{
    dsc_type_t *type = make_uint32_type();
    UINT32 val = 7;
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);

    int rc = DscFormat(&val, sizeof(val), type, NULL, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_STRING("7", DscStrbufCstr(&sb));

    DscStrbufFree(&sb);
    free(type);
}

/* ================================================================== */
/* format_str convenience function                                    */
/* ================================================================== */

void format_str_returns_allocated_string(void)
{
    dsc_type_t *type = make_uint32_type();
    UINT32 val = 99;

    char *result = DscFormatStr(&val, sizeof(val), type, NULL);
    TEST_ASSERT_NOT_NULL(result);
    TEST_ASSERT_EQUAL_STRING("99", result);

    free(result);
    free(type);
}

/* ================================================================== */
/* Format pointer test                                                */
/* ================================================================== */

void format_pointer_hex(void)
{
    dsc_type_t pointee = {0};
    pointee.kind = DSC_TYPE_BASE;
    pointee.name = "uint32_t";
    pointee.byte_size = 4;

    dsc_type_t *type = calloc(1, sizeof(*type));
    type->kind = DSC_TYPE_POINTER;
    type->byte_size = 8;
    type->u.pointer.pointee = &pointee;

    UINT64 addr = 0x20001000;
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);

    DscFormatOpts opts = DscFormatOptsDefault();
    int rc = DscFormat(&addr, sizeof(addr), type, &opts, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_TRUE(strstr(DscStrbufCstr(&sb), "0x") != NULL);

    DscStrbufFree(&sb);
    free(type);
}

/* ================================================================== */
/* Format typedef unwrap test                                         */
/* ================================================================== */

void format_typedef_unwraps(void)
{
    /* typedef -> uint32 base */
    dsc_type_t base = {0};
    base.kind = DSC_TYPE_BASE;
    base.byte_size = 4;
    base.u.base.encoding = DSC_ENC_UNSIGNED;

    dsc_type_t *td = calloc(1, sizeof(*td));
    td->kind = DSC_TYPE_TYPEDEF;
    td->name = "counter_t";
    td->byte_size = 4;
    td->u.modifier.target = &base;

    UINT32 val = 77;
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);
    int rc = DscFormat(&val, sizeof(val), td, NULL, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_STRING("77", DscStrbufCstr(&sb));

    DscStrbufFree(&sb);
    free(td);
}

/* ================================================================== */
/* Format const unwrap test                                           */
/* ================================================================== */

void format_const_unwraps(void)
{
    dsc_type_t base = {0};
    base.kind = DSC_TYPE_BASE;
    base.byte_size = 4;
    base.u.base.encoding = DSC_ENC_UNSIGNED;

    dsc_type_t *ct = calloc(1, sizeof(*ct));
    ct->kind = DSC_TYPE_CONST;
    ct->byte_size = 4;
    ct->u.modifier.target = &base;

    UINT32 val = 0xCAFE;
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);
    int rc = DscFormat(&val, sizeof(val), ct, NULL, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_STRING("51966", DscStrbufCstr(&sb));

    DscStrbufFree(&sb);
    free(ct);
}

/* ================================================================== */
/* Format volatile unwrap test                                        */
/* ================================================================== */

void format_volatile_unwraps(void)
{
    dsc_type_t base = {0};
    base.kind = DSC_TYPE_BASE;
    base.byte_size = 2;
    base.u.base.encoding = DSC_ENC_SIGNED;

    dsc_type_t *vt = calloc(1, sizeof(*vt));
    vt->kind = DSC_TYPE_VOLATILE;
    vt->byte_size = 2;
    vt->u.modifier.target = &base;

    INT16 val = -5;
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);
    int rc = DscFormat(&val, sizeof(val), vt, NULL, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_STRING("-5", DscStrbufCstr(&sb));

    DscStrbufFree(&sb);
    free(vt);
}

/* ================================================================== */
/* Format union test (same as struct display)                         */
/* ================================================================== */

static dsc_type_t s_union_field_type;
static dsc_struct_field_t s_union_fields[2];

void format_union_shows_fields(void)
{
    memset(&s_union_field_type, 0, sizeof(s_union_field_type));
    s_union_field_type.kind = DSC_TYPE_BASE;
    s_union_field_type.byte_size = 4;
    s_union_field_type.u.base.encoding = DSC_ENC_UNSIGNED;

    s_union_fields[0].name = "u32";
    s_union_fields[0].byte_offset = 0;
    s_union_fields[0].type = &s_union_field_type;

    s_union_fields[1].name = "f32";
    s_union_fields[1].byte_offset = 0;
    s_union_fields[1].type = &s_union_field_type;

    dsc_type_t *type = calloc(1, sizeof(*type));
    type->kind = DSC_TYPE_UNION;
    type->byte_size = 4;
    type->u.composite.fields = s_union_fields;
    type->u.composite.field_count = 2;

    UINT32 val = 0xDEADBEEF;
    DscStrbuf sb;
    DscStrbufInit(&sb, 256);
    DscFormatOpts opts = DscFormatOptsDefault();
    int rc = DscFormat(&val, sizeof(val), type, &opts, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);

    const char *result = DscStrbufCstr(&sb);
    TEST_ASSERT_TRUE(strstr(result, ".u32") != NULL);
    TEST_ASSERT_TRUE(strstr(result, ".f32") != NULL);

    DscStrbufFree(&sb);
    free(type);
}

/* ================================================================== */
/* Format bool test                                                   */
/* ================================================================== */

void format_bool_true(void)
{
    dsc_type_t *type = calloc(1, sizeof(*type));
    type->kind = DSC_TYPE_BASE;
    type->byte_size = 1;
    type->u.base.encoding = DSC_ENC_BOOL;

    UINT8 val = 1;
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);
    int rc = DscFormat(&val, sizeof(val), type, NULL, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_STRING("true", DscStrbufCstr(&sb));

    DscStrbufFree(&sb);
    free(type);
}

void format_bool_false(void)
{
    dsc_type_t *type = calloc(1, sizeof(*type));
    type->kind = DSC_TYPE_BASE;
    type->byte_size = 1;
    type->u.base.encoding = DSC_ENC_BOOL;

    UINT8 val = 0;
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);
    int rc = DscFormat(&val, sizeof(val), type, NULL, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    TEST_ASSERT_EQUAL_STRING("false", DscStrbufCstr(&sb));

    DscStrbufFree(&sb);
    free(type);
}

/* ================================================================== */
/* Format float test                                                  */
/* ================================================================== */

void format_float32(void)
{
    dsc_type_t *type = calloc(1, sizeof(*type));
    type->kind = DSC_TYPE_BASE;
    type->byte_size = 4;
    type->u.base.encoding = DSC_ENC_FLOAT;

    float val = 3.14f;
    DscStrbuf sb;
    DscStrbufInit(&sb, 64);
    int rc = DscFormat(&val, sizeof(val), type, NULL, &sb);
    TEST_ASSERT_EQUAL(DSC_OK, rc);
    /* Should contain "3.14" somewhere */
    TEST_ASSERT_TRUE(strstr(DscStrbufCstr(&sb), "3.14") != NULL);

    DscStrbufFree(&sb);
    free(type);
}

/* ================================================================== */
/* Runner                                                             */
/* ================================================================== */

int test_format_main(void)
{
    UNITY_BEGIN();

    /* base types */
    RUN_TEST(format_uint32_decimal);
    RUN_TEST(format_uint32_hex);
    RUN_TEST(format_int16_negative);
    RUN_TEST(format_bool_true);
    RUN_TEST(format_bool_false);
    RUN_TEST(format_float32);

    /* enum */
    RUN_TEST(format_enum_known_value);
    RUN_TEST(format_enum_second_value);

    /* composite */
    RUN_TEST(format_struct_multiline);
    RUN_TEST(format_union_shows_fields);

    /* array */
    RUN_TEST(format_array_elements);

    /* modifiers: typedef / const / volatile */
    RUN_TEST(format_typedef_unwraps);
    RUN_TEST(format_const_unwraps);
    RUN_TEST(format_volatile_unwraps);

    /* pointer */
    RUN_TEST(format_pointer_hex);

    /* misc */
    RUN_TEST(format_null_opts_uses_defaults);
    RUN_TEST(format_str_returns_allocated_string);

    return UNITY_END();
}
