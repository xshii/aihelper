/* PURPOSE: Serial transport — UART 连接，协议逻辑委托给 cmdline 共享层
 * PATTERN: 只实现 termios 连接/断开，协议部分复用 transport_cmdline
 * FOR: 弱 AI 参考如何用 Template Method 消除 transport 间的协议重复 */

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <fcntl.h>
#include <termios.h>
#include <unistd.h>

#include "transport_serial.h"
#include "transport_cmdline.h"
#include "transport_factory.h"
#include "../util/log.h"

/* ---------- IO 回调：POSIX read/write ---------- */

static INT32 fd_send(int fd, const void *buf, UINT32 len)
{
    return write(fd, buf, len);
}

static INT32 fd_recv(int fd, char *ch)
{
    return read(fd, ch, 1);
}

/* ---------- Private struct ---------- */

typedef struct {
    dsc_transport_t   base;       /* MUST be first member */
    dsc_cmdline_ctx_t cmd;        /* 共享协议上下文 */
    char              device[256];
    int               baudrate;
    struct termios    orig_tios;
} serial_transport_t;

static inline serial_transport_t *to_serial(dsc_transport_t *t)
{
    return (serial_transport_t *)t;
}

/* ---------- Baud rate mapping ---------- */

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

/* ---------- Termios 配置 ---------- */

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

    tios.c_cflag |= (CLOCAL | CREAD);
    tios.c_cflag &= ~CSIZE;
    tios.c_cflag |= CS8;
    tios.c_cflag &= ~PARENB;
    tios.c_cflag &= ~CSTOPB;
    tios.c_cflag &= ~CRTSCTS;

    tios.c_iflag &= ~(IXON | IXOFF | IXANY);
    tios.c_iflag &= ~(IGNBRK | BRKINT | PARMRK | ISTRIP |
                       INLCR | IGNCR | ICRNL);

    tios.c_lflag &= ~(ECHO | ECHONL | ICANON | ISIG | IEXTEN);
    tios.c_oflag &= ~OPOST;

    tios.c_cc[VMIN]  = 0;
    tios.c_cc[VTIME] = 0;

    tcflush(fd, TCIFLUSH);
    if (tcsetattr(fd, TCSANOW, &tios) < 0) {
        DSC_LOG_ERROR("tcsetattr(%s): %s", device, strerror(errno));
        return DSC_ERR_TRANSPORT_OPEN;
    }
    return DSC_OK;
}

/* ---------- vtable: open (serial 特有) ---------- */

static int serial_open(dsc_transport_t *self)
{
    serial_transport_t *st = to_serial(self);

    st->cmd.fd = open(st->device, O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (st->cmd.fd < 0) {
        DSC_LOG_ERROR("open(%s): %s", st->device, strerror(errno));
        return DSC_ERR_TRANSPORT_OPEN;
    }

    int flags = fcntl(st->cmd.fd, F_GETFL, 0);
    fcntl(st->cmd.fd, F_SETFL, flags & ~O_NONBLOCK);

    if (tcgetattr(st->cmd.fd, &st->orig_tios) < 0) {
        DSC_LOG_WARN("tcgetattr(%s): %s", st->device, strerror(errno));
    }

    int rc = configure_termios(st->cmd.fd, st->baudrate, st->device);
    if (rc != DSC_OK) {
        close(st->cmd.fd);
        st->cmd.fd = -1;
        return rc;
    }

    DSC_LOG_INFO("serial opened %s @ %d baud", st->device, st->baudrate);
    return DSC_OK;
}

static void serial_close(dsc_transport_t *self)
{
    serial_transport_t *st = to_serial(self);
    if (st->cmd.fd >= 0) {
        if (tcsetattr(st->cmd.fd, TCSANOW, &st->orig_tios) < 0) {
            DSC_LOG_WARN("tcsetattr(%s): %s", st->device, strerror(errno));
        }
        close(st->cmd.fd);
        st->cmd.fd = -1;
    }
}

/* ---------- vtable: 协议操作委托给 cmdline ---------- */

static int serial_mem_read(dsc_transport_t *self, UINT64 addr,
                           void *buf, UINT32 len)
{
    return dsc_cmdline_mem_read(&to_serial(self)->cmd, addr, buf, len);
}

static int serial_mem_write(dsc_transport_t *self, UINT64 addr,
                            const void *buf, UINT32 len)
{
    return dsc_cmdline_mem_write(&to_serial(self)->cmd, addr, buf, len);
}

static int serial_exec_cmd(dsc_transport_t *self, const char *cmd,
                           char *resp, UINT32 resp_len)
{
    return dsc_cmdline_exec(&to_serial(self)->cmd, cmd, resp, resp_len);
}

static void serial_destroy(dsc_transport_t *self)
{
    serial_close(self);
    free(to_serial(self));
}

/* ---------- vtable ---------- */

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
    if (!st) {
        return NULL;
    }

    st->base.ops = &serial_ops;
    snprintf(st->base.name, sizeof(st->base.name), "serial");

    if (cfg && cfg->device) {
        snprintf(st->device, sizeof(st->device), "%s", cfg->device);
    } else {
        snprintf(st->device, sizeof(st->device), "/dev/ttyS0");
    }
    st->baudrate       = (cfg && cfg->baudrate > 0)   ? cfg->baudrate   : 115200;
    st->cmd.fd         = -1;
    st->cmd.timeout_ms = (cfg && cfg->timeout_ms > 0) ? cfg->timeout_ms : 5000;
    st->cmd.io_send    = fd_send;
    st->cmd.io_recv    = fd_recv;

    return &st->base;
}

DSC_TRANSPORT_REGISTER("serial", serial_transport_create)
