/* PURPOSE: Telnet transport — TCP socket command/response protocol for DSP targets
 * PATTERN: Embed base struct as first member, implement vtable, auto-register
 * FOR: 弱 AI 参考如何用 TCP socket 实现 telnet 命令式调试 */

#include "transport_telnet.h"
#include "transport_factory.h"
#include "../util/log.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <arpa/inet.h>
#include <netdb.h>
#include <netinet/tcp.h>
#include <sys/select.h>
#include <sys/socket.h>

/* ---------- Private struct ---------- */

typedef struct {
    dsc_transport_t base;       /* MUST be first member */
    char            host[256];
    int             port;
    int             timeout_ms;
    int             sockfd;     /* -1 when not connected */
} telnet_transport_t;

/* Helper: downcast from base pointer to concrete type */
static inline telnet_transport_t *to_telnet(dsc_transport_t *t)
{
    return (telnet_transport_t *)t;
}

/* ---------- Internal helpers ---------- */

/* Wait for the socket to become readable within timeout_ms.
 * Returns 1 if readable, 0 on timeout, -1 on error. */
static int wait_readable(int fd, int timeout_ms)
{
    fd_set fds;
    FD_ZERO(&fds);
    FD_SET(fd, &fds);

    struct timeval tv;
    tv.tv_sec  = timeout_ms / 1000;
    tv.tv_usec = (timeout_ms % 1000) * 1000;

    int ret = select(fd + 1, &fds, NULL, NULL, &tv);
    if (ret < 0) {
        DSC_LOG_ERROR("select() failed: %s", strerror(errno));
        return -1;
    }
    return ret;  /* 0 = timeout, >0 = readable */
}

/* send_all: retry partial writes until all bytes are sent.
 * Handles EINTR (interrupted by signal) by retrying.
 * Returns DSC_OK on success, DSC_ERR_TRANSPORT_IO on write failure. */
static int send_all(int fd, const void *buf, size_t len)
{
    const char *p = (const char *)buf;
    size_t remaining = len;

    while (remaining > 0) {
        ssize_t n = send(fd, p, remaining, 0);
        if (n < 0) {
            if (errno == EINTR) continue;
            DSC_LOG_ERROR("send() failed: %s", strerror(errno));
            return DSC_ERR_TRANSPORT_IO;
        }
        p += n;
        remaining -= (size_t)n;
    }
    return DSC_OK;
}

/* Read a line (terminated by '\n') into buf.
 * Returns number of bytes read (excluding null terminator), or error code. */
static int recv_line(int fd, int timeout_ms, char *buf, size_t buf_len)
{
    size_t pos = 0;

    while (pos < buf_len - 1) {
        int ready = wait_readable(fd, timeout_ms);
        if (ready < 0) return DSC_ERR_TRANSPORT_IO;
        if (ready == 0) return DSC_ERR_TRANSPORT_TIMEOUT;

        char ch;
        ssize_t n = recv(fd, &ch, 1, 0);
        if (n < 0) {
            if (errno == EINTR) continue;
            return DSC_ERR_TRANSPORT_IO;
        }
        if (n == 0) {
            /* Connection closed */
            break;
        }
        if (ch == '\n') {
            break;
        }
        buf[pos++] = ch;
    }

    /* Strip trailing '\r' if present */
    if (pos > 0 && buf[pos - 1] == '\r') {
        pos--;
    }
    buf[pos] = '\0';
    return (int)pos;
}

/* Send a command string terminated with "\r\n", then read one response line. */
static int send_cmd_recv(telnet_transport_t *tt, const char *cmd,
                         char *resp, size_t resp_len)
{
    /* Build command with CRLF terminator */
    char line[1024];
    int n = snprintf(line, sizeof(line), "%s\r\n", cmd);
    if (n < 0 || (size_t)n >= sizeof(line)) {
        return DSC_ERR_INVALID_ARG;
    }

    DSC_TRY(send_all(tt->sockfd, line, (size_t)n));

    int rc = recv_line(tt->sockfd, tt->timeout_ms, resp, resp_len);
    if (rc < 0) return rc;
    return DSC_OK;
}

/* ---------- vtable implementations ---------- */

static int telnet_open(dsc_transport_t *self)
{
    telnet_transport_t *tt = to_telnet(self);

    /* Resolve hostname */
    struct addrinfo hints, *res;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family   = AF_INET;
    hints.ai_socktype = SOCK_STREAM;

    char port_str[16];
    snprintf(port_str, sizeof(port_str), "%d", tt->port);

    int gai_err = getaddrinfo(tt->host, port_str, &hints, &res);
    if (gai_err != 0) {
        DSC_LOG_ERROR("getaddrinfo(%s:%d): %s", tt->host, tt->port,
                      gai_strerror(gai_err));
        return DSC_ERR_TRANSPORT_OPEN;
    }

    /* Create socket */
    tt->sockfd = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (tt->sockfd < 0) {
        DSC_LOG_ERROR("socket(): %s", strerror(errno));
        freeaddrinfo(res);
        return DSC_ERR_TRANSPORT_OPEN;
    }

    /* Disable Nagle for low-latency command/response */
    int flag = 1;
    setsockopt(tt->sockfd, IPPROTO_TCP, TCP_NODELAY, &flag, sizeof(flag));

    /* Connect */
    if (connect(tt->sockfd, res->ai_addr, res->ai_addrlen) < 0) {
        DSC_LOG_ERROR("connect(%s:%d): %s", tt->host, tt->port, strerror(errno));
        close(tt->sockfd);
        tt->sockfd = -1;
        freeaddrinfo(res);
        return DSC_ERR_TRANSPORT_OPEN;
    }

    freeaddrinfo(res);
    DSC_LOG_INFO("telnet connected to %s:%d", tt->host, tt->port);
    return DSC_OK;
}

static void telnet_close(dsc_transport_t *self)
{
    telnet_transport_t *tt = to_telnet(self);
    if (tt->sockfd >= 0) {
        close(tt->sockfd);
        tt->sockfd = -1;
        DSC_LOG_DEBUG("telnet connection closed");
    }
}

/* mem_read: send "md <addr> <len>" command, parse hex response.
 * Protocol example:
 *   send: "md 0x20000000 16\r\n"
 *   recv: "20000000: 01020304 05060708 090a0b0c 0d0e0f10" */
static int telnet_mem_read(dsc_transport_t *self, uint64_t addr,
                           void *buf, size_t len)
{
    telnet_transport_t *tt = to_telnet(self);
    if (tt->sockfd < 0) return DSC_ERR_TRANSPORT_IO;

    char cmd[128];
    snprintf(cmd, sizeof(cmd), "md 0x%llx %zu",
             (unsigned long long)addr, len);

    char resp[4096];
    DSC_TRY(send_cmd_recv(tt, cmd, resp, sizeof(resp)));

    /* Parse hex words from response.
     * Expected format: "ADDR: HHHHHHHH HHHHHHHH ..."
     * Skip everything before the first ':'. */
    const char *data_start = strchr(resp, ':');
    if (!data_start) {
        DSC_LOG_ERROR("unexpected md response format: %s", resp);
        return DSC_ERR_MEM_READ;
    }
    data_start++;  /* skip ':' */

    uint8_t *out = (uint8_t *)buf;
    size_t written = 0;

    const char *p = data_start;
    while (*p && written < len) {
        /* Skip whitespace */
        while (*p == ' ') p++;
        if (*p == '\0') break;

        /* Parse a 32-bit hex word */
        unsigned long word;
        char *end;
        word = strtoul(p, &end, 16);
        if (end == p) break;  /* no more hex digits */
        p = end;

        /* Store bytes in big-endian order (MSB first, as printed) */
        for (int i = 3; i >= 0 && written < len; i--) {
            out[written++] = (uint8_t)(word >> (i * 8));
        }
    }

    if (written < len) {
        DSC_LOG_WARN("md returned %zu bytes, requested %zu", written, len);
    }
    return DSC_OK;
}

/* mem_write: send "mw <addr> <value>" for each 32-bit word.
 * Protocol: "mw 0x20000000 0x01020304\r\n" -> "OK" */
static int telnet_mem_write(dsc_transport_t *self, uint64_t addr,
                            const void *buf, size_t len)
{
    telnet_transport_t *tt = to_telnet(self);
    if (tt->sockfd < 0) return DSC_ERR_TRANSPORT_IO;

    const uint8_t *src = (const uint8_t *)buf;
    size_t offset = 0;

    while (offset < len) {
        /* Pack up to 4 bytes into a 32-bit word (big-endian) */
        uint32_t word = 0;
        size_t chunk = (len - offset < 4) ? (len - offset) : 4;
        for (size_t i = 0; i < chunk; i++) {
            word |= (uint32_t)src[offset + i] << ((3 - i) * 8);
        }

        char cmd[128];
        snprintf(cmd, sizeof(cmd), "mw 0x%llx 0x%08x",
                 (unsigned long long)(addr + offset), word);

        char resp[256];
        DSC_TRY(send_cmd_recv(tt, cmd, resp, sizeof(resp)));

        offset += chunk;
    }

    return DSC_OK;
}

static int telnet_exec_cmd(dsc_transport_t *self, const char *cmd,
                           char *resp, size_t resp_len)
{
    telnet_transport_t *tt = to_telnet(self);
    if (tt->sockfd < 0) return DSC_ERR_TRANSPORT_IO;

    return send_cmd_recv(tt, cmd, resp, resp_len);
}

static void telnet_destroy(dsc_transport_t *self)
{
    telnet_transport_t *tt = to_telnet(self);
    telnet_close(self);
    free(tt);
}

/* ---------- vtable definition ---------- */

static const dsc_transport_ops telnet_ops = {
    .open      = telnet_open,
    .close     = telnet_close,
    .mem_read  = telnet_mem_read,
    .mem_write = telnet_mem_write,
    .exec_cmd  = telnet_exec_cmd,
    .destroy   = telnet_destroy,
};

/* ---------- Constructor ---------- */

dsc_transport_t *telnet_transport_create(const dsc_transport_config_t *cfg)
{
    telnet_transport_t *tt = calloc(1, sizeof(*tt));
    if (!tt) return NULL;

    /* Wire up vtable and name */
    tt->base.ops = &telnet_ops;
    snprintf(tt->base.name, sizeof(tt->base.name), "telnet");

    /* Copy config with defaults */
    if (cfg && cfg->host) {
        snprintf(tt->host, sizeof(tt->host), "%s", cfg->host);
    } else {
        snprintf(tt->host, sizeof(tt->host), "localhost");
    }
    tt->port       = (cfg && cfg->port > 0)       ? cfg->port       : 23;
    tt->timeout_ms = (cfg && cfg->timeout_ms > 0)  ? cfg->timeout_ms : 5000;
    tt->sockfd     = -1;

    return &tt->base;
}

/* ---------- Auto-registration ---------- */

DSC_TRANSPORT_REGISTER("telnet", telnet_transport_create)
