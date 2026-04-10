/* PURPOSE: Telnet transport — TCP socket 连接，协议逻辑委托给 cmdline 共享层
 * PATTERN: 只实现连接/断开，协议部分复用 transport_cmdline
 * FOR: 弱 AI 参考如何用 Template Method 消除 transport 间的协议重复 */

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <arpa/inet.h>
#include <netdb.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <unistd.h>

#include "transport_telnet.h"
#include "transport_cmdline.h"
#include "transport_factory.h"
#include "../util/log.h"

/* ---------- IO 回调：socket send/recv ---------- */

static INT32 sock_send(int fd, const void *buf, UINT32 len)
{
    return send(fd, buf, len, 0);
}

static INT32 sock_recv(int fd, char *ch)
{
    return recv(fd, ch, 1, 0);
}

/* ---------- Private struct ---------- */

typedef struct {
    DscTransport   base;     /* MUST be first member */
    DscCmdlineCtx cmd;      /* 共享协议上下文 */
    char              host[256];
    int               port;
} telnet_transport_t;

static inline telnet_transport_t *to_telnet(DscTransport *t)
{
    return (telnet_transport_t *)t;
}

/* ---------- vtable: open (telnet 特有) ---------- */

static int telnet_open(DscTransport *self)
{
    telnet_transport_t *tt = to_telnet(self);

    struct addrinfo hints, *res;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family   = AF_INET;
    hints.ai_socktype = SOCK_STREAM;

    char port_str[16];
    snprintf(port_str, sizeof(port_str), "%d", tt->port);

    int gai_err = getaddrinfo(tt->host, port_str, &hints, &res);
    if (gai_err != 0) {
        DSC_LOG_ERROR("getaddrinfo(%s:%d): %s",
                      tt->host, tt->port, gai_strerror(gai_err));
        return DSC_ERR_TRANSPORT_OPEN;
    }

    tt->cmd.fd = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (tt->cmd.fd < 0) {
        DSC_LOG_ERROR("socket(): %s", strerror(errno));
        freeaddrinfo(res);
        return DSC_ERR_TRANSPORT_OPEN;
    }

    int flag = 1;
    setsockopt(tt->cmd.fd, IPPROTO_TCP, TCP_NODELAY, &flag, sizeof(flag));

    if (connect(tt->cmd.fd, res->ai_addr, res->ai_addrlen) < 0) {
        DSC_LOG_ERROR("connect(%s:%d): %s",
                      tt->host, tt->port, strerror(errno));
        close(tt->cmd.fd);
        tt->cmd.fd = -1;
        freeaddrinfo(res);
        return DSC_ERR_TRANSPORT_OPEN;
    }

    freeaddrinfo(res);
    DSC_LOG_INFO("telnet connected to %s:%d", tt->host, tt->port);
    return DSC_OK;
}

/* ---------- vtable: close ---------- */

static void telnet_close(DscTransport *self)
{
    telnet_transport_t *tt = to_telnet(self);
    if (tt->cmd.fd >= 0) {
        close(tt->cmd.fd);
        tt->cmd.fd = -1;
    }
}

/* ---------- vtable: 协议操作全部委托给 cmdline ---------- */

static int telnet_mem_read(DscTransport *self, UINT64 addr,
                           void *buf, UINT32 len)
{
    return DscCmdlineMemRead(&to_telnet(self)->cmd, addr, buf, len);
}

static int telnet_mem_write(DscTransport *self, UINT64 addr,
                            const void *buf, UINT32 len)
{
    return DscCmdlineMemWrite(&to_telnet(self)->cmd, addr, buf, len);
}

static int telnet_exec_cmd(DscTransport *self, const char *cmd,
                           char *resp, UINT32 resp_len)
{
    return DscCmdlineExec(&to_telnet(self)->cmd, cmd, resp, resp_len);
}

static void telnet_destroy(DscTransport *self)
{
    telnet_close(self);
    free(to_telnet(self));
}

/* ---------- vtable ---------- */

static const DscTransportOps telnet_ops = {
    .open      = telnet_open,
    .close     = telnet_close,
    .mem_read  = telnet_mem_read,
    .mem_write = telnet_mem_write,
    .exec_cmd  = telnet_exec_cmd,
    .destroy   = telnet_destroy,
};

/* ---------- Constructor ---------- */

DscTransport *telnet_transport_create(const DscTransportConfig *cfg)
{
    telnet_transport_t *tt = calloc(1, sizeof(*tt));
    if (!tt) {
        return NULL;
    }

    tt->base.ops = &telnet_ops;
    snprintf(tt->base.name, sizeof(tt->base.name), "telnet");

    if (cfg && cfg->host) {
        snprintf(tt->host, sizeof(tt->host), "%s", cfg->host);
    } else {
        snprintf(tt->host, sizeof(tt->host), "localhost");
    }
    tt->port           = (cfg && cfg->port > 0)      ? cfg->port       : 23;
    tt->cmd.fd         = -1;
    tt->cmd.timeout_ms = (cfg && cfg->timeout_ms > 0) ? cfg->timeout_ms : 5000;
    tt->cmd.io_send    = sock_send;
    tt->cmd.io_recv    = sock_recv;

    return &tt->base;
}

DSC_TRANSPORT_REGISTER("telnet", telnet_transport_create)
