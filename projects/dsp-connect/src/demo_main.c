/* PURPOSE: Minimal usage example — Layer 0 zero-config API
 * PATTERN: Single main() that demonstrates the entire pipeline:
 *          open context -> read variable -> print -> close
 * FOR: Weak AI to see the simplest possible usage of dsp-connect */

#include "core/dsc.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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
        params->port = 23; /* default telnet port */
    }
    params->host = hostbuf;
}

static void print_usage(const char *prog)
{
    fprintf(stderr,
        "Usage: %s <elf_file> <var_name> [transport] [host:port]\n\n"
        "Examples:\n"
        "  %s firmware.elf g_counter\n"
        "  %s firmware.elf g_config.mode telnet 192.168.1.100:4444\n",
        prog, prog, prog);
}

int main(int argc, char **argv)
{
    if (argc < 3) {
        print_usage(argv[0]);
        return 1;
    }

    const char *elf_path  = argv[1];
    const char *var_name  = argv[2];
    const char *transport = (argc > 3) ? argv[3] : "shm";

    DscOpenParams params;
    memset(&params, 0, sizeof(params));
    params.elf_path  = elf_path;
    params.transport = transport;

    if (argc > 4 && strcmp(transport, "telnet") == 0) {
        parse_host_port(argv[4], &params);
    }

    DscContext *ctx = DscOpen(&params);
    if (!ctx) {
        fprintf(stderr, "Error: failed to open session\n");
        return 1;
    }

    char buf[4096];
    int rc = DscReadVar(ctx, var_name, buf, sizeof(buf));
    if (rc < 0) {
        fprintf(stderr, "Error: %s\n", DscLastError(ctx));
        DscClose(ctx);
        return 1;
    }

    printf("%s = %s\n", var_name, buf);
    DscClose(ctx);
    return 0;
}
