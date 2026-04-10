/* PURPOSE: 文本命令协议共享实现 — wait/send/recv/md/mw
 * PATTERN: Template Method — 协议逻辑固定，IO 操作通过函数指针注入
 * FOR: 弱 AI 参考如何用函数指针消除 telnet/serial 的重复协议代码 */

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <sys/select.h>

#include "transport_cmdline.h"
#include "../core/dsc_errors.h"
#include "../util/dsc_common.h"
#include "../util/log.h"

/* ------------------------------------------------------------------ */
/* wait_readable: select() 等待 fd 可读                                */
/* ------------------------------------------------------------------ */
int DscCmdlineWaitReadable(int fd, int timeout_ms)
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
int DscCmdlineSendAll(DscCmdlineCtx *ctx, const void *buf, UINT32 len)
{
    const char *p = (const char *)buf;
    UINT32 remaining = len;

    while (remaining > 0) {
        INT32 n = ctx->io_send(ctx->fd, p, remaining);
        if (n < 0) {
            if (errno == EINTR) {
                continue;
            }
            DSC_LOG_ERROR("send failed: %s", strerror(errno));
            return DSC_ERR_TRANSPORT_IO;
        }
        p += n;
        remaining -= (UINT32)n;
    }
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* recv_line: 逐字节读取直到 \n，去除 \r\n                              */
/* ------------------------------------------------------------------ */
int DscCmdlineRecvLine(DscCmdlineCtx *ctx, char *buf, UINT32 buf_len)
{
    UINT32 pos = 0;

    while (pos < buf_len - 1) {
        int ready = DscCmdlineWaitReadable(ctx->fd, ctx->timeout_ms);
        if (ready < 0) {
            return DSC_ERR_TRANSPORT_IO;
        }
        if (ready == 0) {
            return DSC_ERR_TRANSPORT_TIMEOUT;
        }

        char ch;
        INT32 n = ctx->io_recv(ctx->fd, &ch);
        if (n < 0) {
            if (errno == EINTR) {
                continue;
            }
            return DSC_ERR_TRANSPORT_IO;
        }
        if (n == 0) {
            break; /* EOF / connection closed */
        }
        if (ch == '\n') {
            break;
        }
        buf[pos++] = ch;
    }

    if (pos > 0 && buf[pos - 1] == '\r') {
        pos--;
    }
    buf[pos] = '\0';
    return (int)pos;
}

/* ------------------------------------------------------------------ */
/* exec: 发命令(\r\n) + 收一行响应                                     */
/* ------------------------------------------------------------------ */
int DscCmdlineExec(DscCmdlineCtx *ctx, const char *cmd,
                     char *resp, UINT32 resp_len)
{
    char line[1024];
    int n = snprintf(line, sizeof(line), "%s\r\n", cmd);
    if (n < 0 || (UINT32)n >= sizeof(line)) {
        return DSC_ERR_INVALID_ARG;
    }
    DSC_TRY(DscCmdlineSendAll(ctx, line, (UINT32)n));

    int rc = DscCmdlineRecvLine(ctx, resp, resp_len);
    if (rc < 0) {
        return rc;
    }
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* 内部: 解析 "ADDR: HHHHHHHH HHHHHHHH ..." 格式的 hex 响应            */
/* ------------------------------------------------------------------ */
static int parse_hex_response(const char *resp, UINT8 *out, UINT32 len)
{
    const char *data_start = strchr(resp, ':');
    if (!data_start) {
        DSC_LOG_ERROR("unexpected md response format: %s", resp);
        return DSC_ERR_MEM_READ;
    }
    data_start++;

    UINT32 written = 0;
    const char *p = data_start;

    while (*p && written < len) {
        while (*p == ' ') {
            p++;
        }
        if (*p == '\0') {
            break;
        }

        char *end;
        unsigned long word = strtoul(p, &end, 16);
        if (end == p) {
            break;
        }
        p = end;

        /* 按大端顺序存储（打印顺序 = MSB first） */
        for (int i = 3; i >= 0 && written < len; i--) {
            out[written++] = (UINT8)(word >> (i * 8));
        }
    }
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* mem_read: 发 "md <addr> <len>"，解析 hex 响应                       */
/* ------------------------------------------------------------------ */
int DscCmdlineMemRead(DscCmdlineCtx *ctx, UINT64 addr,
                         void *buf, UINT32 len)
{
    if (ctx->fd < 0) {
        return DSC_ERR_TRANSPORT_IO;
    }

    char cmd[128];
    snprintf(cmd, sizeof(cmd), "md 0x%llx %zu",
             (unsigned long long)addr, len);

    char resp[4096];
    DSC_TRY(DscCmdlineExec(ctx, cmd, resp, sizeof(resp)));
    return parse_hex_response(resp, (UINT8 *)buf, len);
}

/* ------------------------------------------------------------------ */
/* 内部: 把字节打包为 32-bit 大端 word                                  */
/* ------------------------------------------------------------------ */
static UINT32 pack_word_be(const UINT8 *src, UINT32 chunk)
{
    UINT32 word = 0;
    for (UINT32 i = 0; i < chunk; i++) {
        word |= (UINT32)src[i] << ((3 - i) * 8);
    }
    return word;
}

/* ------------------------------------------------------------------ */
/* mem_write: 逐 word 发 "mw <addr> <value>"                          */
/* ------------------------------------------------------------------ */
int DscCmdlineMemWrite(DscCmdlineCtx *ctx, UINT64 addr,
                          const void *buf, UINT32 len)
{
    if (ctx->fd < 0) {
        return DSC_ERR_TRANSPORT_IO;
    }

    const UINT8 *src = (const UINT8 *)buf;
    UINT32 offset = 0;

    while (offset < len) {
        UINT32 chunk = (len - offset < 4) ? (len - offset) : 4;
        UINT32 word = pack_word_be(src + offset, chunk);

        char cmd[128];
        snprintf(cmd, sizeof(cmd), "mw 0x%llx 0x%08x",
                 (unsigned long long)(addr + offset), word);

        char resp[256];
        DSC_TRY(DscCmdlineExec(ctx, cmd, resp, sizeof(resp)));
        offset += chunk;
    }
    return DSC_OK;
}
