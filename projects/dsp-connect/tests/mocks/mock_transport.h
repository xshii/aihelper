/* PURPOSE: Mock transport that reads/writes from a local memory buffer
 * PATTERN: vtable implementation backed by uint8_t array, records all calls
 * FOR: Unit tests that need transport without real hardware */

#ifndef MOCK_TRANSPORT_H
#define MOCK_TRANSPORT_H

#include "../../src/transport/transport.h"
#include <stddef.h>
#include <stdint.h>

/* Maximum size of the mock memory buffer */
#define MOCK_MEM_SIZE 4096

/* Call record for verifying transport interactions */
typedef struct {
    int      call_count;
    uint64_t last_addr;
    size_t   last_len;
    int      open_count;
    int      close_count;
} mock_transport_record_t;

/* Create a mock transport backed by an internal buffer.
 * Returns a transport pointer; caller must call mock_transport_destroy(). */
dsc_transport_t *mock_transport_create(void);

/* Destroy a mock transport created by mock_transport_create(). */
void mock_transport_destroy(dsc_transport_t *t);

/* Get pointer to the internal memory buffer for setup/verification. */
uint8_t *mock_transport_get_memory(dsc_transport_t *t);

/* Get the call record for verification after test. */
const mock_transport_record_t *mock_transport_get_record(dsc_transport_t *t);

/* Pre-fill memory at a given offset with data. */
void mock_transport_set_memory(dsc_transport_t *t,
                               uint64_t addr, const void *data, size_t len);

/* Reset call records and optionally clear memory. */
void mock_transport_reset(dsc_transport_t *t, int clear_memory);

#endif /* MOCK_TRANSPORT_H */
