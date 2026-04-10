/* PURPOSE: Master header — the one header users include for dsp-connect
 * PATTERN: Opaque context + Layer 0 zero-config API + Layer 1 options
 * FOR: Weak AI to reference when designing a top-level C library facade */

#ifndef DSC_H
#define DSC_H

#include "dsc_errors.h"
#include <stddef.h>
#include <stdint.h>

/* ------------------------------------------------------------------ */
/* Opaque context — holds all session state                           */
/* ------------------------------------------------------------------ */
typedef struct dsc_context_t dsc_context_t;

/* ------------------------------------------------------------------ */
/* Layer 0: Zero-config open                                          */
/* ------------------------------------------------------------------ */

typedef struct {
    const char *elf_path;         /* REQUIRED: path to ELF with DWARF    */
    const char *transport;        /* Transport name: "telnet", "serial", "shm" */
    const char *arch;             /* Arch name: "byte_le", "byte_be", "word16" etc */
    /* Transport config */
    const char *host;             /* telnet: host/IP                     */
    int         port;             /* telnet: port                        */
    const char *device;           /* serial: device path                 */
    int         baudrate;         /* serial: baud rate                   */
    const char *shm_path;         /* shm: file path                     */
    size_t      shm_size;         /* shm: region size                   */
    int         timeout_ms;       /* I/O timeout (0 = backend default)   */
} dsc_open_params_t;

/* Open a debug session.
 * Returns context handle on success, NULL on failure.
 * On failure, reason is logged via DSC_LOG_ERROR. */
dsc_context_t *dsc_open(const dsc_open_params_t *params);

/* Close session and free all resources. Safe to call with NULL. */
void dsc_close(dsc_context_t *ctx);

/* ------------------------------------------------------------------ */
/* Layer 0: One-call variable read                                    */
/* ------------------------------------------------------------------ */

/* Read a variable by path, format it, write result to caller buffer.
 * Path examples: "g_counter", "g_config.mode", "g_buf[3].x"
 * Returns DSC_OK on success, negative dsc_error_t on failure. */
int dsc_read_var(dsc_context_t *ctx, const char *var_path,
                 char *out, size_t out_len);

/* ------------------------------------------------------------------ */
/* Layer 1: Read with format options                                  */
/* ------------------------------------------------------------------ */

/* Forward declare — actual definition lives in format/format.h */
typedef struct dsc_format_opts_t dsc_format_opts_t;

/* Same as dsc_read_var but with custom formatting.
 * Pass NULL for opts to get default formatting. */
int dsc_read_var_ex(dsc_context_t *ctx, const char *var_path,
                    const dsc_format_opts_t *opts,
                    char *out, size_t out_len);

/* ------------------------------------------------------------------ */
/* Layer 1: Raw memory access                                         */
/* ------------------------------------------------------------------ */

/* Read raw bytes from logical address. */
int dsc_read_mem(dsc_context_t *ctx, uint64_t addr,
                 void *buf, size_t len);

/* Write raw bytes to logical address. */
int dsc_write_mem(dsc_context_t *ctx, uint64_t addr,
                  const void *buf, size_t len);

/* ------------------------------------------------------------------ */
/* Error context                                                      */
/* ------------------------------------------------------------------ */

/* Returns last error message for this context.
 * The returned pointer is valid until the next API call on this ctx. */
const char *dsc_last_error(const dsc_context_t *ctx);

/* ------------------------------------------------------------------ */
/* Utility                                                            */
/* ------------------------------------------------------------------ */

/* Reload ELF (e.g. after reflash).
 * Closes DWARF, reopens the same path, reloads symbols,
 * invalidates resolve cache. Transport stays connected.
 * Returns DSC_OK on success. */
int dsc_reload(dsc_context_t *ctx);

#endif /* DSC_H */
