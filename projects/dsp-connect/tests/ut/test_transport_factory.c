/* PURPOSE: Tests for transport factory — registration and creation */

#include "test_helper.h"
#include "../src/transport/transport.h"
#include "../src/transport/transport_factory.h"
#include "../src/core/dsc_errors.h"

#include <stdlib.h>
#include <string.h>

/* --- Dummy transport for factory tests --- */

typedef struct {
    dsc_transport_t base;
    int             created;
} dummy_transport_t;

static int dummy_open(dsc_transport_t *self)
{
    (void)self;
    return DSC_OK;
}

static void dummy_close(dsc_transport_t *self) { (void)self; }

static int dummy_mem_read(dsc_transport_t *self, uint64_t addr,
                          void *buf, size_t len)
{
    (void)self; (void)addr; (void)buf; (void)len;
    return DSC_OK;
}

static int dummy_mem_write(dsc_transport_t *self, uint64_t addr,
                           const void *buf, size_t len)
{
    (void)self; (void)addr; (void)buf; (void)len;
    return DSC_OK;
}

static int dummy_exec_cmd(dsc_transport_t *self, const char *cmd,
                          char *resp, size_t resp_len)
{
    (void)self; (void)cmd; (void)resp; (void)resp_len;
    return DSC_OK;
}

static void dummy_destroy(dsc_transport_t *self) { free(self); }

static const dsc_transport_ops dummy_ops = {
    .open      = dummy_open,
    .close     = dummy_close,
    .mem_read  = dummy_mem_read,
    .mem_write = dummy_mem_write,
    .exec_cmd  = dummy_exec_cmd,
    .destroy   = dummy_destroy,
};

static dsc_transport_t *dummy_ctor(const dsc_transport_config_t *cfg)
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

TEST(factory_register_and_create)
{
    int rc = dsc_transport_register("test_dummy", dummy_ctor);
    ASSERT_EQ(rc, DSC_OK);

    dsc_transport_t *t = dsc_transport_create("test_dummy", NULL);
    ASSERT_NOT_NULL(t);

    dummy_transport_t *d = (dummy_transport_t *)t;
    ASSERT_EQ(d->created, 1);

    dsc_transport_free(t);
}

TEST(factory_unknown_name_returns_null)
{
    dsc_transport_t *t = dsc_transport_create("no_such_backend", NULL);
    ASSERT_NULL(t);
}

TEST(factory_null_name_returns_null)
{
    dsc_transport_t *t = dsc_transport_create(NULL, NULL);
    ASSERT_NULL(t);
}

TEST(factory_register_null_name_fails)
{
    int rc = dsc_transport_register(NULL, dummy_ctor);
    ASSERT_EQ(rc, DSC_ERR_INVALID_ARG);
}

TEST(factory_register_null_ctor_fails)
{
    int rc = dsc_transport_register("valid_name", NULL);
    ASSERT_EQ(rc, DSC_ERR_INVALID_ARG);
}

TEST(factory_list_registered)
{
    /* "test_dummy" was registered in an earlier test */
    const char *names[16];
    int count = dsc_transport_list(names, 16);
    ASSERT(count >= 1);

    /* Verify our test_dummy is in the list */
    int found = 0;
    for (int i = 0; i < count; i++) {
        if (strcmp(names[i], "test_dummy") == 0) {
            found = 1;
        }
    }
    ASSERT(found);
}

/* ================================================================== */
/* Runner                                                             */
/* ================================================================== */

int test_transport_factory_main(void)
{
    printf("=== test_transport_factory ===\n");

    RUN_TEST(factory_register_and_create);
    RUN_TEST(factory_unknown_name_returns_null);
    RUN_TEST(factory_null_name_returns_null);
    RUN_TEST(factory_register_null_name_fails);
    RUN_TEST(factory_register_null_ctor_fails);
    RUN_TEST(factory_list_registered);

    TEST_SUMMARY();
}
