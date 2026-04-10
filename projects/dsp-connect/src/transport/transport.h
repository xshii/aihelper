/* PURPOSE: Abstract transport interface — vtable-based polymorphism for target access
 * PATTERN: vtable (struct of function pointers) as first member enables static dispatch
 * FOR: Weak AI to reference how to build a polymorphic C interface without C++ */

#ifndef DSC_TRANSPORT_H
#define DSC_TRANSPORT_H

#include "../util/types.h"
#include <stddef.h>
#include <stdint.h>

#include "../core/dsc_errors.h"
#include "../util/dsc_common.h"

/* ---------- Forward declarations ---------- */

typedef struct DscTransport    DscTransport;
typedef struct DscTransportOps  DscTransportOps;

/* ---------- Virtual table ---------- */

/* Every concrete transport implements this table.
 * All functions receive the base struct pointer — the implementation casts it
 * to its private struct (whose first member IS a DscTransport). */
struct DscTransportOps {
    int  (*open)(DscTransport *self);
    void (*close)(DscTransport *self);
    int  (*mem_read)(DscTransport *self, UINT64 addr, void *buf, UINT32 len);
    int  (*mem_write)(DscTransport *self, UINT64 addr, const void *buf, UINT32 len);
    int  (*exec_cmd)(DscTransport *self, const char *cmd, char *resp, UINT32 resp_len);
    void (*destroy)(DscTransport *self);
};

/* ---------- Base "class" ---------- */

/* Concrete implementations embed this as their FIRST member so that
 * (DscTransport *)ptr and (concrete_t *)ptr have the same address. */
struct DscTransport {
    const DscTransportOps *ops;
    char name[32];
};

/* ---------- Transport creation config ---------- */

/* Transport creation config — single struct covers all backends.
 * Each backend reads ONLY the fields it needs:
 *   telnet:  host, port, timeout_ms
 *   serial:  device, baudrate, timeout_ms
 *   shm:     shm_path, shm_size, timeout_ms
 * Unused fields are ignored (zero-initialized is safe). */
typedef struct {
    const char *host;       /* telnet: hostname / IP              */
    int         port;       /* telnet: TCP port (default 23)      */
    const char *device;     /* serial: device path e.g. /dev/ttyS0 */
    int         baudrate;   /* serial: baud rate (default 115200) */
    const char *shm_path;   /* shm: shared memory file path       */
    UINT32      shm_size;   /* shm: region size in bytes          */
    int         timeout_ms; /* I/O timeout, 0 = use backend default */
} DscTransportConfig;

/* ---------- Convenience inline wrappers ---------- */

/* These dispatch through the vtable so callers never touch ->ops directly. */

static inline int DscTransportOpen(DscTransport *t)
{
    return t->ops->open(t);
}

static inline void DscTransportClose(DscTransport *t)
{
    t->ops->close(t);
}

static inline int DscTransportMemRead(DscTransport *t,
                                         UINT64 addr, void *buf, UINT32 len)
{
    return t->ops->mem_read(t, addr, buf, len);
}

static inline int DscTransportMemWrite(DscTransport *t,
                                          UINT64 addr, const void *buf, UINT32 len)
{
    return t->ops->mem_write(t, addr, buf, len);
}

static inline int DscTransportExecCmd(DscTransport *t,
                                         const char *cmd, char *resp, UINT32 resp_len)
{
    return t->ops->exec_cmd(t, cmd, resp, resp_len);
}

static inline void DscTransportDestroy(DscTransport *t)
{
    if (t && t->ops->destroy) {
        t->ops->destroy(t);
    }
}

#endif /* DSC_TRANSPORT_H */
