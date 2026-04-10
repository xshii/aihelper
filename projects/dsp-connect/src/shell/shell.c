/* PURPOSE: 交互式命令解释器实现
 * PATTERN: 前缀匹配分派 → 变量查询 / 内置命令 / 转发
 * FOR: 弱 AI 参考如何构建命令行调试 Shell */

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>

#include "shell.h"
#include "../core/dsc.h"
#include "../core/dsc_errors.h"
#include "../util/log.h"
#include "../util/strbuf.h"

/* ------------------------------------------------------------------ */
/* Shell context                                                      */
/* ------------------------------------------------------------------ */

struct DscShell {
    DscContext *ctx;
};

DscShell *DscShellCreate(DscContext *ctx)
{
    if (!ctx) {
        return NULL;
    }
    DscShell *sh = calloc(1, sizeof(*sh));
    if (!sh) {
        return NULL;
    }
    sh->ctx = ctx;
    return sh;
}

void DscShellDestroy(DscShell *sh)
{
    free(sh);
}

/* ------------------------------------------------------------------ */
/* 内部: 去除首尾空白                                                   */
/* ------------------------------------------------------------------ */

static char *strip(char *s)
{
    while (*s && isspace((unsigned char)*s)) {
        s++;
    }
    char *end = s + strlen(s);
    while (end > s && isspace((unsigned char)end[-1])) {
        end--;
    }
    *end = '\0';
    return s;
}

/* ------------------------------------------------------------------ */
/* 内置命令: help                                                      */
/* ------------------------------------------------------------------ */

static DscShellResult cmd_help(char *out, UINT32 out_len)
{
    snprintf(out, out_len,
        "Commands:\n"
        "  <varname>              Read variable (e.g. g_config.mode)\n"
        "  d <addr> <len>         Display memory at address\n"
        "  w <addr> <value>       Write 32-bit value to address\n"
        "  call <func> <p1>,<p2>  Call function on target\n"
        "  reload                 Reload ELF symbols\n"
        "  help                   Show this help\n"
        "  quit                   Exit shell\n");
    return DSC_SHELL_OK;
}

/* ------------------------------------------------------------------ */
/* 内置命令: d <addr> <len> — 显示内存                                   */
/* ------------------------------------------------------------------ */

static DscShellResult cmd_display(DscShell *sh, const char *args,
                                  char *out, UINT32 out_len)
{
    UINT64 addr = 0;
    UINT32 len = 16; /* 默认 16 字节 */

    /* 解析地址（支持 0x 前缀和 &var 语法） */
    if (sscanf(args, "%llx %u", (unsigned long long *)&addr, &len) < 1) {
        snprintf(out, out_len, "Usage: d <addr> [len]");
        return DSC_SHELL_ERROR;
    }

    if (len > 1024) {
        len = 1024;
    }

    UINT8 buf[1024];
    int rc = DscReadMem(sh->ctx, addr, buf, len);
    if (rc < 0) {
        snprintf(out, out_len, "Error: %s", DscLastError(sh->ctx));
        return DSC_SHELL_ERROR;
    }

    /* hex dump 格式化 */
    DscStrbuf sb;
    DscStrbufInit(&sb, 512);
    for (UINT32 i = 0; i < len; i += 16) {
        DscStrbufAppendf(&sb, "%08llx: ", (unsigned long long)(addr + i));
        for (UINT32 j = 0; j < 16 && (i + j) < len; j++) {
            DscStrbufAppendf(&sb, "%02x ", buf[i + j]);
        }
        DscStrbufAppend(&sb, "\n");
    }
    snprintf(out, out_len, "%s", DscStrbufCstr(&sb));
    DscStrbufFree(&sb);
    return DSC_SHELL_OK;
}

/* ------------------------------------------------------------------ */
/* 内置命令: w <addr> <value> — 写内存                                   */
/* ------------------------------------------------------------------ */

static DscShellResult cmd_write(DscShell *sh, const char *args,
                                char *out, UINT32 out_len)
{
    UINT64 addr = 0;
    UINT32 value = 0;

    if (sscanf(args, "%llx %x",
               (unsigned long long *)&addr, &value) < 2) {
        snprintf(out, out_len, "Usage: w <addr> <value>");
        return DSC_SHELL_ERROR;
    }

    int rc = DscWriteMem(sh->ctx, addr, &value, sizeof(value));
    if (rc < 0) {
        snprintf(out, out_len, "Error: %s", DscLastError(sh->ctx));
        return DSC_SHELL_ERROR;
    }
    snprintf(out, out_len, "OK: wrote 0x%08x to 0x%llx",
             value, (unsigned long long)addr);
    return DSC_SHELL_OK;
}

/* ------------------------------------------------------------------ */
/* 内置命令: call <func> <p1>,<p2> — 远程函数调用                        */
/* ------------------------------------------------------------------ */

static DscShellResult cmd_call(DscShell *sh, const char *args,
                               char *out, UINT32 out_len)
{
    /* 转发 "call func p1,p2" 给 transport */
    char cmd[512];
    snprintf(cmd, sizeof(cmd), "call %s", args);

    char resp[4096];
    int rc = DscExecCmd(sh->ctx, cmd, resp, sizeof(resp));
    if (rc < 0) {
        snprintf(out, out_len, "Error: %s", DscLastError(sh->ctx));
        return DSC_SHELL_ERROR;
    }
    snprintf(out, out_len, "%s", resp);
    return DSC_SHELL_OK;
}

/* ------------------------------------------------------------------ */
/* 内置命令: reload — 重新加载 ELF 符号表                                */
/* ------------------------------------------------------------------ */

static DscShellResult cmd_reload(DscShell *sh, char *out, UINT32 out_len)
{
    int rc = DscReload(sh->ctx);
    if (rc < 0) {
        snprintf(out, out_len, "Error: %s", DscLastError(sh->ctx));
        return DSC_SHELL_ERROR;
    }
    snprintf(out, out_len, "OK: symbols reloaded");
    return DSC_SHELL_OK;
}

/* ------------------------------------------------------------------ */
/* 变量查询: 输入变量名，打印值和地址                                     */
/* ------------------------------------------------------------------ */

static DscShellResult cmd_read_var(DscShell *sh, const char *varname,
                                   char *out, UINT32 out_len)
{
    char val_buf[4096];
    int rc = DscReadVar(sh->ctx, varname, val_buf, sizeof(val_buf));
    if (rc < 0) {
        snprintf(out, out_len, "Error: %s", DscLastError(sh->ctx));
        return DSC_SHELL_ERROR;
    }
    snprintf(out, out_len, "%s = %s", varname, val_buf);
    return DSC_SHELL_OK;
}

/* ------------------------------------------------------------------ */
/* 命令分派器                                                          */
/* ------------------------------------------------------------------ */

DscShellResult DscShellExec(DscShell *sh, const char *input,
                            char *out, UINT32 out_len)
{
    if (!sh || !input || !out || out_len == 0) {
        return DSC_SHELL_ERROR;
    }

    /* 复制输入以便修改 */
    char line[1024];
    snprintf(line, sizeof(line), "%s", input);
    char *cmd = strip(line);

    if (cmd[0] == '\0') {
        out[0] = '\0';
        return DSC_SHELL_OK;
    }

    /* 内置命令匹配 */
    if (strcmp(cmd, "quit") == 0 || strcmp(cmd, "q") == 0) {
        snprintf(out, out_len, "Bye.");
        return DSC_SHELL_QUIT;
    }
    if (strcmp(cmd, "help") == 0 || strcmp(cmd, "?") == 0) {
        return cmd_help(out, out_len);
    }
    if (strcmp(cmd, "reload") == 0) {
        return cmd_reload(sh, out, out_len);
    }
    if (strncmp(cmd, "d ", 2) == 0) {
        return cmd_display(sh, cmd + 2, out, out_len);
    }
    if (strncmp(cmd, "w ", 2) == 0) {
        return cmd_write(sh, cmd + 2, out, out_len);
    }
    if (strncmp(cmd, "call ", 5) == 0) {
        return cmd_call(sh, cmd + 5, out, out_len);
    }

    /* 默认: 当作变量名查询 */
    return cmd_read_var(sh, cmd, out, out_len);
}

/* ------------------------------------------------------------------ */
/* 交互式循环 (stdin → stdout)                                        */
/* ------------------------------------------------------------------ */

void DscShellLoop(DscShell *sh)
{
    char input[1024];
    char output[8192];

    printf("dsc> ");
    fflush(stdout);

    while (fgets(input, sizeof(input), stdin)) {
        DscShellResult res = DscShellExec(sh, input, output, sizeof(output));
        if (output[0] != '\0') {
            printf("%s\n", output);
        }
        if (res == DSC_SHELL_QUIT) {
            break;
        }
        printf("dsc> ");
        fflush(stdout);
    }
}

/* ------------------------------------------------------------------ */
/* Socket 服务: 监听端口，接受连接后进入命令循环                          */
/* ------------------------------------------------------------------ */

static int handle_client(DscShell *sh, int client_fd)
{
    char input[1024];
    char output[8192];
    char prompt[] = "dsc> ";

    send(client_fd, prompt, strlen(prompt), 0);

    /* 逐行读取命令 */
    UINT32 pos = 0;
    char ch;
    while (recv(client_fd, &ch, 1, 0) == 1) {
        if (ch == '\n') {
            input[pos] = '\0';
            pos = 0;

            DscShellResult res = DscShellExec(sh, input,
                                              output, sizeof(output));
            if (output[0] != '\0') {
                send(client_fd, output, strlen(output), 0);
                send(client_fd, "\n", 1, 0);
            }
            if (res == DSC_SHELL_QUIT) {
                return 0;
            }
            send(client_fd, prompt, strlen(prompt), 0);
        } else if (ch != '\r' && pos < sizeof(input) - 1) {
            input[pos++] = ch;
        }
    }
    return 0;
}

int DscShellServe(DscShell *sh, int port)
{
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) {
        DSC_LOG_ERROR("socket(): failed");
        return DSC_ERR_TRANSPORT_OPEN;
    }

    int opt = 1;
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons((UINT16)port);

    if (bind(server_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        DSC_LOG_ERROR("bind(%d): failed", port);
        close(server_fd);
        return DSC_ERR_TRANSPORT_OPEN;
    }

    if (listen(server_fd, 1) < 0) {
        DSC_LOG_ERROR("listen(): failed");
        close(server_fd);
        return DSC_ERR_TRANSPORT_OPEN;
    }

    DSC_LOG_INFO("shell listening on port %d", port);

    int client_fd = accept(server_fd, NULL, NULL);
    if (client_fd < 0) {
        DSC_LOG_ERROR("accept(): failed");
        close(server_fd);
        return DSC_ERR_TRANSPORT_IO;
    }

    DSC_LOG_INFO("shell client connected");
    handle_client(sh, client_fd);

    close(client_fd);
    close(server_fd);
    return DSC_OK;
}
