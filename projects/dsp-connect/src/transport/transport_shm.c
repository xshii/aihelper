/* PURPOSE: Shared memory transport — mmap-based direct memory access for simulator/FPGA
 * PATTERN: Embed base struct as first member, implement vtable, auto-register
 * FOR: 弱 AI 参考如何用 mmap 实现共享内存直接读写 */

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#include "transport_shm.h"
#include "transport_factory.h"
#include "../util/log.h"

/* ---------- Doorbell layout ---------- */

/* Optional doorbell mechanism for synchronization.
 * The first page of the shared memory region is reserved for control:
 *
 *   offset 0x00: cmd_doorbell  (UINT32) — host writes 1 to signal command ready
 *   offset 0x04: rsp_doorbell  (UINT32) — target writes 1 to signal response ready
 *   offset 0x08: cmd_buf       (char[504]) — command string from host
 *   offset 0x200: rsp_buf      (char[512]) — response string from target
 *
 * Actual target memory starts at offset SHM_DATA_OFFSET.
 */

#define SHM_CTRL_SIZE     4096   /* first page reserved for control */
#define SHM_DATA_OFFSET   SHM_CTRL_SIZE

#define SHM_OFF_CMD_BELL  0x00
#define SHM_OFF_RSP_BELL  0x04
#define SHM_OFF_CMD_BUF   0x08
#define SHM_CMD_BUF_SIZE  504
#define SHM_OFF_RSP_BUF   0x200
#define SHM_RSP_BUF_SIZE  512

/* ---------- Private struct ---------- */

typedef struct {
    DscTransport base;       /* MUST be first member */
    char            shm_path[256];
    UINT32          shm_size;   /* total mmap size (ctrl + data) */
    int             timeout_ms;
    int             fd;         /* file descriptor for the shm file */
    UINT8        *map;        /* mmap base pointer, NULL when not mapped */
} shm_transport_t;

static inline shm_transport_t *to_shm(DscTransport *t)
{
    return (shm_transport_t *)t;
}

/* ---------- Internal helpers ---------- */

/* Read a volatile uint32 from the mapped region. */
static inline UINT32 shm_read32(const UINT8 *base, UINT32 offset)
{
    volatile const UINT32 *p = (volatile const UINT32 *)(base + offset);
    return *p;
}

/* Write a volatile uint32 to the mapped region. */
static inline void shm_write32(UINT8 *base, UINT32 offset, UINT32 val)
{
    volatile UINT32 *p = (volatile UINT32 *)(base + offset);
    *p = val;
}

/* Poll the response doorbell until it becomes non-zero or timeout.
 * Returns DSC_OK on success, DSC_ERR_TRANSPORT_TIMEOUT on timeout. */
static int shm_wait_doorbell(shm_transport_t *st)
{
    int elapsed_us = 0;
    int limit_us   = st->timeout_ms * 1000;

    while (elapsed_us < limit_us) {
        if (shm_read32(st->map, SHM_OFF_RSP_BELL) != 0) {
            /* Clear the response doorbell */
            shm_write32(st->map, SHM_OFF_RSP_BELL, 0);
            return DSC_OK;
        }
        /* Spin with a small sleep to avoid burning CPU */
        usleep(100);
        elapsed_us += 100;
    }

    return DSC_ERR_TRANSPORT_TIMEOUT;
}

/* ---------- vtable implementations ---------- */

static int shm_tp_open(DscTransport *self)
{
    shm_transport_t *st = to_shm(self);

    st->fd = open(st->shm_path, O_RDWR);
    if (st->fd < 0) {
        /* Try to create the file if it does not exist */
        st->fd = open(st->shm_path, O_RDWR | O_CREAT, 0666);
        if (st->fd < 0) {
            DSC_LOG_ERROR("open(%s): %s", st->shm_path, strerror(errno));
            return DSC_ERR_TRANSPORT_OPEN;
        }
        /* Extend file to required size */
        if (ftruncate(st->fd, (off_t)st->shm_size) < 0) {
            DSC_LOG_ERROR("ftruncate(%s, %zu): %s",
                          st->shm_path, st->shm_size, strerror(errno));
            close(st->fd);
            st->fd = -1;
            return DSC_ERR_TRANSPORT_OPEN;
        }
    }

    st->map = mmap(NULL, st->shm_size, PROT_READ | PROT_WRITE,
                   MAP_SHARED, st->fd, 0);
    if (st->map == MAP_FAILED) {
        DSC_LOG_ERROR("mmap(%s, %zu): %s",
                      st->shm_path, st->shm_size, strerror(errno));
        st->map = NULL;
        close(st->fd);
        st->fd = -1;
        return DSC_ERR_TRANSPORT_OPEN;
    }

    /* Clear the control region */
    memset(st->map, 0, SHM_CTRL_SIZE);

    DSC_LOG_INFO("shm mapped %s (%zu bytes, data offset 0x%x)",
                 st->shm_path, st->shm_size, SHM_DATA_OFFSET);
    return DSC_OK;
}

static void shm_tp_close(DscTransport *self)
{
    shm_transport_t *st = to_shm(self);

    if (st->map) {
        munmap(st->map, st->shm_size);
        st->map = NULL;
    }
    if (st->fd >= 0) {
        close(st->fd);
        st->fd = -1;
    }
    DSC_LOG_DEBUG("shm unmapped");
}

/* mem_read: direct memcpy from the shared memory data region.
 * addr is treated as an offset into the data region. */
static int shm_mem_read(DscTransport *self, UINT64 addr,
                        void *buf, UINT32 len)
{
    shm_transport_t *st = to_shm(self);
    if (!st->map) {
        return DSC_ERR_TRANSPORT_IO;
    }

    UINT32 data_size = st->shm_size - SHM_DATA_OFFSET;
    if (addr + len > data_size) {
        DSC_LOG_ERROR("shm read out of bounds: offset 0x%llx + %zu > %zu",
                      (unsigned long long)addr, len, data_size);
        return DSC_ERR_MEM_READ;
    }

    memcpy(buf, st->map + SHM_DATA_OFFSET + addr, len);
    return DSC_OK;
}

/* mem_write: direct memcpy into the shared memory data region. */
static int shm_mem_write(DscTransport *self, UINT64 addr,
                         const void *buf, UINT32 len)
{
    shm_transport_t *st = to_shm(self);
    if (!st->map) {
        return DSC_ERR_TRANSPORT_IO;
    }

    UINT32 data_size = st->shm_size - SHM_DATA_OFFSET;
    if (addr + len > data_size) {
        DSC_LOG_ERROR("shm write out of bounds: offset 0x%llx + %zu > %zu",
                      (unsigned long long)addr, len, data_size);
        return DSC_ERR_MEM_WRITE;
    }

    memcpy(st->map + SHM_DATA_OFFSET + addr, buf, len);
    return DSC_OK;
}

/* exec_cmd: write command to shared buffer, ring doorbell, wait for response. */
static int shm_exec_cmd(DscTransport *self, const char *cmd,
                        char *resp, UINT32 resp_len)
{
    shm_transport_t *st = to_shm(self);
    if (!st->map) {
        return DSC_ERR_TRANSPORT_IO;
    }

    /* Write command string into the command buffer */
    UINT32 cmd_len = strlen(cmd);
    if (cmd_len >= SHM_CMD_BUF_SIZE) {
        DSC_LOG_ERROR("command too long for shm buffer: %zu >= %d",
                      cmd_len, SHM_CMD_BUF_SIZE);
        return DSC_ERR_INVALID_ARG;
    }
    memcpy(st->map + SHM_OFF_CMD_BUF, cmd, cmd_len + 1);

    /* Ring the command doorbell */
    shm_write32(st->map, SHM_OFF_CMD_BELL, 1);

    /* Wait for the target to respond */
    DSC_TRY(shm_wait_doorbell(st));

    /* Copy response */
    const char *rsp_src = (const char *)(st->map + SHM_OFF_RSP_BUF);
    UINT32 copy_len = strlen(rsp_src);
    if (copy_len >= resp_len) {
        copy_len = resp_len - 1;
    }
    memcpy(resp, rsp_src, copy_len);
    resp[copy_len] = '\0';

    return DSC_OK;
}

static void shm_destroy(DscTransport *self)
{
    shm_transport_t *st = to_shm(self);
    shm_tp_close(self);
    free(st);
}

/* ---------- vtable definition ---------- */

static const DscTransportOps shm_ops = {
    .open      = shm_tp_open,
    .close     = shm_tp_close,
    .mem_read  = shm_mem_read,
    .mem_write = shm_mem_write,
    .exec_cmd  = shm_exec_cmd,
    .destroy   = shm_destroy,
};

/* ---------- Constructor ---------- */

#define SHM_DEFAULT_SIZE (1024 * 1024 + SHM_CTRL_SIZE)  /* 1 MiB data + ctrl page */

DscTransport *shm_transport_create(const DscTransportConfig *cfg)
{
    shm_transport_t *st = calloc(1, sizeof(*st));
    if (!st) {
        return NULL;
    }

    st->base.ops = &shm_ops;
    snprintf(st->base.name, sizeof(st->base.name), "shm");

    if (cfg && cfg->shm_path) {
        snprintf(st->shm_path, sizeof(st->shm_path), "%s", cfg->shm_path);
    } else {
        snprintf(st->shm_path, sizeof(st->shm_path), "/tmp/dsc_shm");
    }

    st->shm_size   = (cfg && cfg->shm_size > 0)
                         ? cfg->shm_size + SHM_CTRL_SIZE
                         : SHM_DEFAULT_SIZE;
    st->timeout_ms = (cfg && cfg->timeout_ms > 0) ? cfg->timeout_ms : 5000;
    st->fd         = -1;
    st->map        = NULL;

    return &st->base;
}

/* ---------- Auto-registration ---------- */

DSC_TRANSPORT_REGISTER("shm", shm_transport_create)
