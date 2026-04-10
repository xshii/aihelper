/* PURPOSE: 演示程序 — 支持单次查询和交互式 Shell 两种模式
 * PATTERN: Layer 0 API + Shell 交互层
 * FOR: Weak AI to see the simplest usage of dsp-connect */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "core/dsc.h"
#include "shell/shell.h"

/* Parse "host:port" into params. Uses static buffer. */
static void parse_host_port(const char *arg, DscOpenParams *params)
{
    static char hostbuf[256];
    snprintf(hostbuf, sizeof(hostbuf), "%s", arg);
    char *colon = strchr(hostbuf, ':');
    if (colon) {
        *colon = '\0';
        params->port = atoi(colon + 1);
    } else {
        params->port = 23;
    }
    params->host = hostbuf;
}

static void print_usage(const char *prog)
{
    fprintf(stderr,
        "Usage:\n"
        "  %s <elf> shell [transport] [host:port]     Interactive shell\n"
        "  %s <elf> <varname> [transport] [host:port]  Single query\n"
        "\nExamples:\n"
        "  %s firmware.elf shell telnet 192.168.1.100:4444\n"
        "  %s firmware.elf g_config.mode telnet 192.168.1.100:4444\n",
        prog, prog, prog, prog);
}

static DscContext *open_session(int argc, char **argv)
{
    const char *transport = (argc > 3) ? argv[3] : "shm";

    DscOpenParams params;
    memset(&params, 0, sizeof(params));
    params.elf_path  = argv[1];
    params.transport = transport;
    params.arch      = "byte_le";

    if (argc > 4 && strcmp(transport, "telnet") == 0) {
        parse_host_port(argv[4], &params);
    }
    return DscOpen(&params);
}

int main(int argc, char **argv)
{
    if (argc < 3) {
        print_usage(argv[0]);
        return 1;
    }

    DscContext *ctx = open_session(argc, argv);
    if (!ctx) {
        fprintf(stderr, "Error: failed to open session\n");
        return 1;
    }

    if (strcmp(argv[2], "shell") == 0) {
        /* 交互式 Shell 模式 */
        DscShell *sh = DscShellCreate(ctx);
        DscShellLoop(sh);
        DscShellDestroy(sh);
    } else {
        /* 单次变量查询 */
        char buf[4096];
        int rc = DscReadVar(ctx, argv[2], buf, sizeof(buf));
        if (rc < 0) {
            fprintf(stderr, "Error: %s\n", DscLastError(ctx));
            DscClose(ctx);
            return 1;
        }
        printf("%s = %s\n", argv[2], buf);
    }

    DscClose(ctx);
    return 0;
}
