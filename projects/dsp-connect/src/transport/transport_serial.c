/* PURPOSE: Serial transport — UART-based command/response protocol for DSP targets
 * PATTERN: Embed base struct as first member, implement vtable, auto-register
 * FOR: 弱 AI 参考如何用 termios 实现串口通信 */

#include "transport_serial.h"
#include "transport_factory.h"
#include "../util/log.h"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <sys/select.h>
#include <termios.h>

/* ---------- Private struct ---------- */

typedef struct {
    dsc_transport_t base;       /* MUST be first member */
    char            device[256];
    int             baudrate;
    int             timeout_ms;
    int             fd;         /* -1 when not open */
    struct termios  orig_tios;  /* saved original terminal settings */
} serial_transport_t;

static inline serial_transport_t *to_serial(dsc_transport_t *t)
{
    return (serial_transport_t *)t;
}

/* ---------- Baud rate mapping ---------- */

/* Map integer baud rate to termios speed constant.
 * Returns B0 (invalid) if the rate is not supported. */
static speed_t baud_to_speed(int baudrate)
{
    switch (baudrate) {
    case 9600:   return B9600;
    case 19200:  return B19200;
    case 38400:  return B38400;
    case 57600:  return B57600;
    case 115200: return B115200;
    case 230400: return B230400;
#ifdef B460800
    case 460800: return B460800;
#endif
#ifdef B921600
    case 921600: return B921600;
#endif
    default:     return B0;
    }
}

/* ---------- Internal helpers ---------- */

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
    return ret;
}

/* send_all: retry partial writes until all bytes are sent.
 * Handles EINTR (interrupted by signal) by retrying.
 * Returns DSC_OK on success, DSC_ERR_TRANSPORT_IO on write failure. */
static int send_all(int fd, const void *buf, size_t len)
{
    const char *p = (const char *)buf;
    size_t remaining = len;

    while (remaining > 0) {
        ssize_t n = write(fd, p, remaining);
        if (n < 0) {
            if (errno == EINTR) continue;
            DSC_LOG_ERROR("write() failed: %s", strerror(errno));
            return DSC_ERR_TRANSPORT_IO;
        }
        p += n;
        remaining -= (size_t)n;
    }
    return DSC_OK;
}

static int recv_line(int fd, int timeout_ms, char *buf, size_t buf_len)
{
    size_t pos = 0;

    while (pos < buf_len - 1) {
        int ready = wait_readable(fd, timeout_ms);
        if (ready < 0) return DSC_ERR_TRANSPORT_IO;
        if (ready == 0) return DSC_ERR_TRANSPORT_TIMEOUT;

        char ch;
        ssize_t n = read(fd, &ch, 1);
        if (n < 0) {
            if (errno == EINTR) continue;
            return DSC_ERR_TRANSPORT_IO;
        }
        if (n == 0) break;
        if (ch == '\n') break;
        buf[pos++] = ch;
    }

    if (pos > 0 && buf[pos - 1] == '\r') {
        pos--;
    }
    buf[pos] = '\0';
    return (int)pos;
}

static int send_cmd_recv(serial_transport_t *st, const char *cmd,
                         char *resp, size_t resp_len)
{
    char line[1024];
    int n = snprintf(line, sizeof(line), "%s\r\n", cmd);
    if (n < 0 || (size_t)n >= sizeof(line)) {
        return DSC_ERR_INVALID_ARG;
    }

    DSC_TRY(send_all(st->fd, line, (size_t)n));

    int rc = recv_line(st->fd, st->timeout_ms, resp, resp_len);
    if (rc < 0) return rc;
    return DSC_OK;
}

/* ---------- vtable implementations ---------- */

/* Configure termios for raw 8N1 mode at the given baud rate.
 * Returns DSC_OK on success, or an error code on failure. */
static int configure_termios(int fd, int baudrate, const char *device)
{
    struct termios tios;
    memset(&tios, 0, sizeof(tios));

    speed_t speed = baud_to_speed(baudrate);
    if (speed == B0) {
        DSC_LOG_ERROR("unsupported baud rate: %d", baudrate);
        return DSC_ERR_INVALID_ARG;
    }

    cfsetispeed(&tios, speed);
    cfsetospeed(&tios, speed);

    tios.c_cflag |= (CLOCAL | CREAD);  /* enable receiver, ignore modem status */
    tios.c_cflag &= ~CSIZE;
    tios.c_cflag |= CS8;               /* 8 data bits */
    tios.c_cflag &= ~PARENB;           /* no parity */
    tios.c_cflag &= ~CSTOPB;           /* 1 stop bit */
    tios.c_cflag &= ~CRTSCTS;          /* no hardware flow control */

    tios.c_iflag &= ~(IXON | IXOFF | IXANY);   /* no software flow control */
    tios.c_iflag &= ~(IGNBRK | BRKINT | PARMRK | ISTRIP |
                       INLCR | IGNCR | ICRNL);  /* raw input */

    tios.c_lflag &= ~(ECHO | ECHONL | ICANON | ISIG | IEXTEN);  /* raw mode */
    tios.c_oflag &= ~OPOST;            /* raw output */

    tios.c_cc[VMIN]  = 0;              /* non-blocking read */
    tios.c_cc[VTIME] = 0;

    tcflush(fd, TCIFLUSH);
    if (tcsetattr(fd, TCSANOW, &tios) < 0) {
        DSC_LOG_ERROR("tcsetattr(%s): %s", device, strerror(errno));
        return DSC_ERR_TRANSPORT_OPEN;
    }
    return DSC_OK;
}

static int serial_open(dsc_transport_t *self)
{
    serial_transport_t *st = to_serial(self);

    st->fd = open(st->device, O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (st->fd < 0) {
        DSC_LOG_ERROR("open(%s): %s", st->device, strerror(errno));
        return DSC_ERR_TRANSPORT_OPEN;
    }

    /* Clear non-blocking after open (we use select for timeout) */
    int flags = fcntl(st->fd, F_GETFL, 0);
    fcntl(st->fd, F_SETFL, flags & ~O_NONBLOCK);

    /* Save original settings */
    tcgetattr(st->fd, &st->orig_tios);

    /* Configure raw mode */
    int rc = configure_termios(st->fd, st->baudrate, st->device);
    if (rc != DSC_OK) {
        close(st->fd);
        st->fd = -1;
        return rc;
    }

    DSC_LOG_INFO("serial opened %s @ %d baud", st->device, st->baudrate);
    return DSC_OK;
}

static void serial_close(dsc_transport_t *self)
{
    serial_transport_t *st = to_serial(self);
    if (st->fd >= 0) {
        tcsetattr(st->fd, TCSANOW, &st->orig_tios);  /* restore settings */
        close(st->fd);
        st->fd = -1;
        DSC_LOG_DEBUG("serial connection closed");
    }
}

/* Same command protocol as telnet: "md <addr> <len>" -> hex response */
static int serial_mem_read(dsc_transport_t *self, uint64_t addr,
                           void *buf, size_t len)
{
    serial_transport_t *st = to_serial(self);
    if (st->fd < 0) return DSC_ERR_TRANSPORT_IO;

    char cmd[128];
    snprintf(cmd, sizeof(cmd), "md 0x%llx %zu",
             (unsigned long long)addr, len);

    char resp[4096];
    DSC_TRY(send_cmd_recv(st, cmd, resp, sizeof(resp)));

    /* Parse hex words — same format as telnet backend */
    const char *data_start = strchr(resp, ':');
    if (!data_start) {
        DSC_LOG_ERROR("unexpected md response: %s", resp);
        return DSC_ERR_MEM_READ;
    }
    data_start++;

    uint8_t *out = (uint8_t *)buf;
    size_t written = 0;
    const char *p = data_start;

    while (*p && written < len) {
        while (*p == ' ') p++;
        if (*p == '\0') break;

        unsigned long word;
        char *end;
        word = strtoul(p, &end, 16);
        if (end == p) break;
        p = end;

        for (int i = 3; i >= 0 && written < len; i--) {
            out[written++] = (uint8_t)(word >> (i * 8));
        }
    }

    return DSC_OK;
}

static int serial_mem_write(dsc_transport_t *self, uint64_t addr,
                            const void *buf, size_t len)
{
    serial_transport_t *st = to_serial(self);
    if (st->fd < 0) return DSC_ERR_TRANSPORT_IO;

    const uint8_t *src = (const uint8_t *)buf;
    size_t offset = 0;

    while (offset < len) {
        uint32_t word = 0;
        size_t chunk = (len - offset < 4) ? (len - offset) : 4;
        for (size_t i = 0; i < chunk; i++) {
            word |= (uint32_t)src[offset + i] << ((3 - i) * 8);
        }

        char cmd[128];
        snprintf(cmd, sizeof(cmd), "mw 0x%llx 0x%08x",
                 (unsigned long long)(addr + offset), word);

        char resp[256];
        DSC_TRY(send_cmd_recv(st, cmd, resp, sizeof(resp)));
        offset += chunk;
    }

    return DSC_OK;
}

static int serial_exec_cmd(dsc_transport_t *self, const char *cmd,
                           char *resp, size_t resp_len)
{
    serial_transport_t *st = to_serial(self);
    if (st->fd < 0) return DSC_ERR_TRANSPORT_IO;

    return send_cmd_recv(st, cmd, resp, resp_len);
}

static void serial_destroy(dsc_transport_t *self)
{
    serial_transport_t *st = to_serial(self);
    serial_close(self);
    free(st);
}

/* ---------- vtable definition ---------- */

static const dsc_transport_ops serial_ops = {
    .open      = serial_open,
    .close     = serial_close,
    .mem_read  = serial_mem_read,
    .mem_write = serial_mem_write,
    .exec_cmd  = serial_exec_cmd,
    .destroy   = serial_destroy,
};

/* ---------- Constructor ---------- */

dsc_transport_t *serial_transport_create(const dsc_transport_config_t *cfg)
{
    serial_transport_t *st = calloc(1, sizeof(*st));
    if (!st) return NULL;

    st->base.ops = &serial_ops;
    snprintf(st->base.name, sizeof(st->base.name), "serial");

    if (cfg && cfg->device) {
        snprintf(st->device, sizeof(st->device), "%s", cfg->device);
    } else {
        snprintf(st->device, sizeof(st->device), "/dev/ttyS0");
    }
    st->baudrate   = (cfg && cfg->baudrate > 0)   ? cfg->baudrate   : 115200;
    st->timeout_ms = (cfg && cfg->timeout_ms > 0)  ? cfg->timeout_ms : 5000;
    st->fd         = -1;

    return &st->base;
}

/* ---------- Auto-registration ---------- */

DSC_TRANSPORT_REGISTER("serial", serial_transport_create)
