/* PURPOSE: 文本命令协议共享实现 — wait/send/recv/md/mw
 * PATTERN: Template Method — 协议逻辑固定，IO 操作通过函数指针注入
 * FOR: 弱 AI 参考如何用函数指针消除 telnet/serial 的重复协议代码 */

#include "transport_cmdline.h"
#include "../core/dsc_errors.h"
#include "../util/log.h"
#include "../util/dsc_common.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>

/* ------------------------------------------------------------------ */
/* wait_readable: select() 等待 fd 可读                                */
/* ------------------------------------------------------------------ */
int dsc_cmdline_wait_readable(int fd, int timeout_ms)
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
    return ret; /* 0 = timeout, >0 = readable */
}

/* ------------------------------------------------------------------ */
/* send_all: 通过 io_send 回调重试发送直到全部写出                       */
/* ------------------------------------------------------------------ */
int dsc_cmdline_send_all(dsc_cmdline_ctx_t *ctx, const void *buf, size_t len)
{
    const char *p = (const char *)buf;
    size_t remaining = len;

    while (remaining > 0) {
        ssize_t n = ctx->io_send(ctx->fd, p, remaining);
        if (n < 0) {
            if (errno == EINTR) continue;
            DSC_LOG_ERROR("send failed: %s", strerror(errno));
            return DSC_ERR_TRANSPORT_IO;
        }
        p += n;
        remaining -= (size_t)n;
    }
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* recv_line: 逐字节读取直到 \n，去除 \r\n                              */
/* ------------------------------------------------------------------ */
int dsc_cmdline_recv_line(dsc_cmdline_ctx_t *ctx, char *buf, size_t buf_len)
{
    size_t pos = 0;

    while (pos < buf_len - 1) {
        int ready = dsc_cmdline_wait_readable(ctx->fd, ctx->timeout_ms);
        if (ready < 0) return DSC_ERR_TRANSPORT_IO;
        if (ready == 0) return DSC_ERR_TRANSPORT_TIMEOUT;

        char ch;
        ssize_t n = ctx->io_recv(ctx->fd, &ch);
        if (n < 0) {
            if (errno == EINTR) continue;
            return DSC_ERR_TRANSPORT_IO;
        }
        if (n == 0) break; /* EOF / connection closed */
        if (ch == '\n') break;
        buf[pos++] = ch;
    }

    if (pos > 0 && buf[pos - 1] == '\r') pos--;
    buf[pos] = '\0';
    return (int)pos;
}

/* ------------------------------------------------------------------ */
/* exec: 发命令(\r\n) + 收一行响应                                     */
/* ------------------------------------------------------------------ */
int dsc_cmdline_exec(dsc_cmdline_ctx_t *ctx, const char *cmd,
                     char *resp, size_t resp_len)
{
    char line[1024];
    int n = snprintf(line, sizeof(line), "%s\r\n", cmd);
    if (n < 0 || (size_t)n >= sizeof(line)) {
        return DSC_ERR_INVALID_ARG;
    }
    DSC_TRY(dsc_cmdline_send_all(ctx, line, (size_t)n));

    int rc = dsc_cmdline_recv_line(ctx, resp, resp_len);
    if (rc < 0) return rc;
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* 内部: 解析 "ADDR: HHHHHHHH HHHHHHHH ..." 格式的 hex 响应            */
/* ------------------------------------------------------------------ */
static int parse_hex_response(const char *resp, uint8_t *out, size_t len)
{
    const char *data_start = strchr(resp, ':');
    if (!data_start) {
        DSC_LOG_ERROR("unexpected md response format: %s", resp);
        return DSC_ERR_MEM_READ;
    }
    data_start++;

    size_t written = 0;
    const char *p = data_start;

    while (*p && written < len) {
        while (*p == ' ') p++;
        if (*p == '\0') break;

        char *end;
        unsigned long word = strtoul(p, &end, 16);
        if (end == p) break;
        p = end;

        /* 按大端顺序存储（打印顺序 = MSB first） */
        for (int i = 3; i >= 0 && written < len; i--) {
            out[written++] = (uint8_t)(word >> (i * 8));
        }
    }
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* mem_read: 发 "md <addr> <len>"，解析 hex 响应                       */
/* ------------------------------------------------------------------ */
int dsc_cmdline_mem_read(dsc_cmdline_ctx_t *ctx, uint64_t addr,
                         void *buf, size_t len)
{
    if (ctx->fd < 0) return DSC_ERR_TRANSPORT_IO;

    char cmd[128];
    snprintf(cmd, sizeof(cmd), "md 0x%llx %zu",
             (unsigned long long)addr, len);

    char resp[4096];
    DSC_TRY(dsc_cmdline_exec(ctx, cmd, resp, sizeof(resp)));
    return parse_hex_response(resp, (uint8_t *)buf, len);
}

/* ------------------------------------------------------------------ */
/* 内部: 把字节打包为 32-bit 大端 word                                  */
/* ------------------------------------------------------------------ */
static uint32_t pack_word_be(const uint8_t *src, size_t chunk)
{
    uint32_t word = 0;
    for (size_t i = 0; i < chunk; i++) {
        word |= (uint32_t)src[i] << ((3 - i) * 8);
    }
    return word;
}

/* ------------------------------------------------------------------ */
/* mem_write: 逐 word 发 "mw <addr> <value>"                          */
/* ------------------------------------------------------------------ */
int dsc_cmdline_mem_write(dsc_cmdline_ctx_t *ctx, uint64_t addr,
                          const void *buf, size_t len)
{
    if (ctx->fd < 0) return DSC_ERR_TRANSPORT_IO;

    const uint8_t *src = (const uint8_t *)buf;
    size_t offset = 0;

    while (offset < len) {
        size_t chunk = (len - offset < 4) ? (len - offset) : 4;
        uint32_t word = pack_word_be(src + offset, chunk);

        char cmd[128];
        snprintf(cmd, sizeof(cmd), "mw 0x%llx 0x%08x",
                 (unsigned long long)(addr + offset), word);

        char resp[256];
        DSC_TRY(dsc_cmdline_exec(ctx, cmd, resp, sizeof(resp)));
        offset += chunk;
    }
    return DSC_OK;
}
