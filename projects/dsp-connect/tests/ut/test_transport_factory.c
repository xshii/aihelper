/* PURPOSE: Tests for transport factory — registration and creation */

#include "unity/unity.h"
#include "../src/transport/transport.h"
#include "../src/transport/transport_factory.h"
#include "../src/core/dsc_errors.h"

#include <stdlib.h>
#include <string.h>

/* --- Dummy transport for factory tests --- */

typedef struct {
    DscTransport base;
    int             created;
} dummy_transport_t;

static int dummy_open(DscTransport *self)
{
    (void)self;
    return DSC_OK;
}

static void dummy_close(DscTransport *self) { (void)self; }

static int dummy_mem_read(DscTransport *self, UINT64 addr,
                          void *buf, UINT32 len)
{
    (void)self; (void)addr; (void)buf; (void)len;
    return DSC_OK;
}

static int dummy_mem_write(DscTransport *self, UINT64 addr,
                           const void *buf, UINT32 len)
{
    (void)self; (void)addr; (void)buf; (void)len;
    return DSC_OK;
}

static int dummy_exec_cmd(DscTransport *self, const char *cmd,
                          char *resp, UINT32 resp_len)
{
    (void)self; (void)cmd; (void)resp; (void)resp_len;
    return DSC_OK;
}

static void dummy_destroy(DscTransport *self) { free(self); }

static const DscTransportOps dummy_ops = {
    .open      = dummy_open,
    .close     = dummy_close,
    .mem_read  = dummy_mem_read,
    .mem_write = dummy_mem_write,
    .exec_cmd  = dummy_exec_cmd,
    .destroy   = dummy_destroy,
};

static DscTransport *dummy_ctor(const DscTransportConfig *cfg)
{
    (void)cfg;
    dummy_transport_t *d = calloc(1, sizeof(*d));
    if (!d) return NULL;
    d->base.ops = &dummy_ops;
    memcpy(d->base.name, "dummy", 6);
    d->created = 1;
    return &d->base;
}


/* ================================================================== */
/* Tests                                                              */
/* ================================================================== */

void factory_register_and_create(void)
{
    int rc = DscTransportRegister("test_dummy", dummy_ctor);
    TEST_ASSERT_EQUAL(DSC_OK, rc);

    DscTransport *t = DscTransportCreate("test_dummy", NULL);
    TEST_ASSERT_NOT_NULL(t);

    dummy_transport_t *d = (dummy_transport_t *)t;
    TEST_ASSERT_EQUAL(1, d->created);

    dsc_transport_free(t);
}

void factory_unknown_name_returns_null(void)
{
    DscTransport *t = DscTransportCreate("no_such_backend", NULL);
    TEST_ASSERT_NULL(t);
}

void factory_null_name_returns_null(void)
{
    DscTransport *t = DscTransportCreate(NULL, NULL);
    TEST_ASSERT_NULL(t);
}

void factory_register_null_name_fails(void)
{
    int rc = DscTransportRegister(NULL, dummy_ctor);
    TEST_ASSERT_EQUAL(DSC_ERR_INVALID_ARG, rc);
}

void factory_register_null_ctor_fails(void)
{
    int rc = DscTransportRegister("valid_name", NULL);
    TEST_ASSERT_EQUAL(DSC_ERR_INVALID_ARG, rc);
}

void factory_list_registered(void)
{
    /* "test_dummy" was registered in an earlier test */
    const char *names[16];
    int count = DscTransportList(names, 16);
    TEST_ASSERT_TRUE(count >= 1);

    /* Verify our test_dummy is in the list */
    int found = 0;
    for (int i = 0; i < count; i++) {
        if (strcmp(names[i], "test_dummy") == 0) {
            found = 1;
        }
    }
    TEST_ASSERT_TRUE(found);
}

/* ================================================================== */
/* Runner                                                             */
/* ================================================================== */

int test_transport_factory_main(void)
{
    UNITY_BEGIN();

    RUN_TEST(factory_register_and_create);
    RUN_TEST(factory_unknown_name_returns_null);
    RUN_TEST(factory_null_name_returns_null);
    RUN_TEST(factory_register_null_name_fails);
    RUN_TEST(factory_register_null_ctor_fails);
    RUN_TEST(factory_list_registered);

    return UNITY_END();
}
