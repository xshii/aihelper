/* PURPOSE: Mock transport implementation — memory buffer with call recording */

#include "mock_transport.h"
#include <stdlib.h>
#include <string.h>

/* --- Private data structure --- */
typedef struct {
    DscTransport       base;    /* MUST be first member */
    UINT8               mem[MOCK_MEM_SIZE];
    mock_transport_record_t record;
} mock_transport_impl_t;

/* --- vtable: open --- */
static int mock_open(DscTransport *self)
{
    mock_transport_impl_t *m = (mock_transport_impl_t *)self;
    m->record.open_count++;
    return DSC_OK;
}

/* --- vtable: close --- */
static void mock_close(DscTransport *self)
{
    mock_transport_impl_t *m = (mock_transport_impl_t *)self;
    m->record.close_count++;
}

/* --- vtable: mem_read --- */
static int mock_mem_read(DscTransport *self, UINT64 addr,
                         void *buf, UINT32 len)
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
static int mock_mem_write(DscTransport *self, UINT64 addr,
                          const void *buf, UINT32 len)
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
static int mock_exec_cmd(DscTransport *self, const char *cmd,
                         char *resp, UINT32 resp_len)
{
    (void)self; (void)cmd;
    if (resp && resp_len > 0) {
        resp[0] = '\0';
    }
    return DSC_OK;
}

/* --- vtable: destroy --- */
static void mock_destroy(DscTransport *self)
{
    free(self);
}

/* --- Shared ops table --- */
static const DscTransportOps mock_ops = {
    .open      = mock_open,
    .close     = mock_close,
    .mem_read  = mock_mem_read,
    .mem_write = mock_mem_write,
    .exec_cmd  = mock_exec_cmd,
    .destroy   = mock_destroy,
};

/* --- Public API --- */

DscTransport *mock_transport_create(void)
{
    mock_transport_impl_t *m = calloc(1, sizeof(*m));
    if (!m) return NULL;

    m->base.ops = &mock_ops;
    memcpy(m->base.name, "mock", 5);
    return &m->base;
}

void mock_transport_destroy(DscTransport *t)
{
    free(t);
}

UINT8 *mock_transport_get_memory(DscTransport *t)
{
    mock_transport_impl_t *m = (mock_transport_impl_t *)t;
    return m->mem;
}

const mock_transport_record_t *mock_transport_get_record(DscTransport *t)
{
    mock_transport_impl_t *m = (mock_transport_impl_t *)t;
    return &m->record;
}

void mock_transport_set_memory(DscTransport *t,
                               UINT64 addr, const void *data, UINT32 len)
{
    mock_transport_impl_t *m = (mock_transport_impl_t *)t;
    if (addr + len <= MOCK_MEM_SIZE) {
        memcpy(m->mem + addr, data, len);
    }
}

void mock_transport_reset(DscTransport *t, int clear_memory)
{
    mock_transport_impl_t *m = (mock_transport_impl_t *)t;
    memset(&m->record, 0, sizeof(m->record));
    if (clear_memory) {
        memset(m->mem, 0, MOCK_MEM_SIZE);
    }
}
