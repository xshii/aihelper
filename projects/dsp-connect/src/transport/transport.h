/* PURPOSE: Abstract transport interface — vtable-based polymorphism for target access
 * PATTERN: vtable (struct of function pointers) as first member enables static dispatch
 * FOR: Weak AI to reference how to build a polymorphic C interface without C++ */

#ifndef DSC_TRANSPORT_H
#define DSC_TRANSPORT_H

#include <stddef.h>
#include <stdint.h>

#include "../core/dsc_errors.h"
#include "../util/dsc_common.h"

/* ---------- Forward declarations ---------- */

typedef struct dsc_transport_t    dsc_transport_t;
typedef struct dsc_transport_ops  dsc_transport_ops;

/* ---------- Virtual table ---------- */

/* Every concrete transport implements this table.
 * All functions receive the base struct pointer — the implementation casts it
 * to its private struct (whose first member IS a dsc_transport_t). */
struct dsc_transport_ops {
    int  (*open)(dsc_transport_t *self);
    void (*close)(dsc_transport_t *self);
    int  (*mem_read)(dsc_transport_t *self, uint64_t addr, void *buf, size_t len);
    int  (*mem_write)(dsc_transport_t *self, uint64_t addr, const void *buf, size_t len);
    int  (*exec_cmd)(dsc_transport_t *self, const char *cmd, char *resp, size_t resp_len);
    void (*destroy)(dsc_transport_t *self);
};

/* ---------- Base "class" ---------- */

/* Concrete implementations embed this as their FIRST member so that
 * (dsc_transport_t *)ptr and (concrete_t *)ptr have the same address. */
struct dsc_transport_t {
    const dsc_transport_ops *ops;
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
    size_t      shm_size;   /* shm: region size in bytes          */
    int         timeout_ms; /* I/O timeout, 0 = use backend default */
} dsc_transport_config_t;

/* ---------- Convenience inline wrappers ---------- */

/* These dispatch through the vtable so callers never touch ->ops directly. */

static inline int dsc_transport_open(dsc_transport_t *t)
{
    return t->ops->open(t);
}

static inline void dsc_transport_close(dsc_transport_t *t)
{
    t->ops->close(t);
}

static inline int dsc_transport_mem_read(dsc_transport_t *t,
                                         uint64_t addr, void *buf, size_t len)
{
    return t->ops->mem_read(t, addr, buf, len);
}

static inline int dsc_transport_mem_write(dsc_transport_t *t,
                                          uint64_t addr, const void *buf, size_t len)
{
    return t->ops->mem_write(t, addr, buf, len);
}

static inline int dsc_transport_exec_cmd(dsc_transport_t *t,
                                         const char *cmd, char *resp, size_t resp_len)
{
    return t->ops->exec_cmd(t, cmd, resp, resp_len);
}

static inline void dsc_transport_destroy(dsc_transport_t *t)
{
    if (t && t->ops->destroy) {
        t->ops->destroy(t);
    }
}

#endif /* DSC_TRANSPORT_H */
