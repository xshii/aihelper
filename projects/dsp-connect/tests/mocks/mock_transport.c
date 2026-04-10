/* PURPOSE: Mock transport implementation — memory buffer with call recording */

#include "mock_transport.h"
#include <stdlib.h>
#include <string.h>

/* --- Private data structure --- */
typedef struct {
    dsc_transport_t       base;    /* MUST be first member */
    uint8_t               mem[MOCK_MEM_SIZE];
    mock_transport_record_t record;
} mock_transport_impl_t;

/* --- vtable: open --- */
static int mock_open(dsc_transport_t *self)
{
    mock_transport_impl_t *m = (mock_transport_impl_t *)self;
    m->record.open_count++;
    return DSC_OK;
}

/* --- vtable: close --- */
static void mock_close(dsc_transport_t *self)
{
    mock_transport_impl_t *m = (mock_transport_impl_t *)self;
    m->record.close_count++;
}

/* --- vtable: mem_read --- */
static int mock_mem_read(dsc_transport_t *self, uint64_t addr,
                         void *buf, size_t len)
{
    mock_transport_impl_t *m = (mock_transport_impl_t *)self;
    m->record.call_count++;
    m->record.last_addr = addr;
    m->record.last_len = len;

    if (addr + len > MOCK_MEM_SIZE) {
        return DSC_ERR_TRANSPORT_IO;
    }
    memcpy(buf, m->mem + addr, len);
    return DSC_OK;
}

/* --- vtable: mem_write --- */
static int mock_mem_write(dsc_transport_t *self, uint64_t addr,
                          const void *buf, size_t len)
{
    mock_transport_impl_t *m = (mock_transport_impl_t *)self;
    m->record.call_count++;
    m->record.last_addr = addr;
    m->record.last_len = len;

    if (addr + len > MOCK_MEM_SIZE) {
        return DSC_ERR_TRANSPORT_IO;
    }
    memcpy(m->mem + addr, buf, len);
    return DSC_OK;
}

/* --- vtable: exec_cmd --- */
static int mock_exec_cmd(dsc_transport_t *self, const char *cmd,
                         char *resp, size_t resp_len)
{
    (void)self; (void)cmd;
    if (resp && resp_len > 0) {
        resp[0] = '\0';
    }
    return DSC_OK;
}

/* --- vtable: destroy --- */
static void mock_destroy(dsc_transport_t *self)
{
    free(self);
}

/* --- Shared ops table --- */
static const dsc_transport_ops mock_ops = {
    .open      = mock_open,
    .close     = mock_close,
    .mem_read  = mock_mem_read,
    .mem_write = mock_mem_write,
    .exec_cmd  = mock_exec_cmd,
    .destroy   = mock_destroy,
};

/* --- Public API --- */

dsc_transport_t *mock_transport_create(void)
{
    mock_transport_impl_t *m = calloc(1, sizeof(*m));
    if (!m) return NULL;

    m->base.ops = &mock_ops;
    memcpy(m->base.name, "mock", 5);
    return &m->base;
}

void mock_transport_destroy(dsc_transport_t *t)
{
    free(t);
}

uint8_t *mock_transport_get_memory(dsc_transport_t *t)
{
    mock_transport_impl_t *m = (mock_transport_impl_t *)t;
    return m->mem;
}

const mock_transport_record_t *mock_transport_get_record(dsc_transport_t *t)
{
    mock_transport_impl_t *m = (mock_transport_impl_t *)t;
    return &m->record;
}

void mock_transport_set_memory(dsc_transport_t *t,
                               uint64_t addr, const void *data, size_t len)
{
    mock_transport_impl_t *m = (mock_transport_impl_t *)t;
    if (addr + len <= MOCK_MEM_SIZE) {
        memcpy(m->mem + addr, data, len);
    }
}

void mock_transport_reset(dsc_transport_t *t, int clear_memory)
{
    mock_transport_impl_t *m = (mock_transport_impl_t *)t;
    memset(&m->record, 0, sizeof(m->record));
    if (clear_memory) {
        memset(m->mem, 0, MOCK_MEM_SIZE);
    }
}
