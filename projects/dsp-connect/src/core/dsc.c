/* PURPOSE: Core glue layer — wires together dwarf, transport, arch, resolve,
 *          memory, and format into a single opaque context
 * PATTERN: Facade — one context struct holds all sub-system handles,
 *          public functions chain: resolve → mem_read → format
 * FOR: Weak AI to reference when building a top-level integration layer */

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "dsc.h"
#include "dsc_errors.h"
#include "../arch/arch.h"
#include "../arch/arch_factory.h"
#include "../dwarf/dwarf_parser.h"
#include "../dwarf/dwarf_symbols.h"
#include "../format/format.h"
#include "../memory/memory.h"
#include "../resolve/resolve.h"
#include "../resolve/resolve_cache.h"
#include "../transport/transport.h"
#include "../transport/transport_factory.h"
#include "../util/log.h"

/* ------------------------------------------------------------------ */
/* Error buffer size for last_error                                   */
/* ------------------------------------------------------------------ */
#define DSC_ERR_BUF_SIZE 512

/* Default resolve cache capacity */
#define DSC_CACHE_CAPACITY 1024

/* ------------------------------------------------------------------ */
/* Context struct — holds all sub-system handles                      */
/* ------------------------------------------------------------------ */
struct DscContext {
    /* Sub-systems (all owned) */
    dsc_dwarf_t           *dwarf;
    dsc_symtab_t           symtab;
    DscTransport       *transport;
    DscArch            *arch;
    DscResolveCache   *cache;

    /* Config snapshot for reload */
    char                  *elf_path;

    /* Last error message */
    char                   last_error[DSC_ERR_BUF_SIZE];
};

/* ------------------------------------------------------------------ */
/* Internal: set last error message                                   */
/* ------------------------------------------------------------------ */
static void set_error(DscContext *ctx, const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(ctx->last_error, DSC_ERR_BUF_SIZE, fmt, ap);
    va_end(ap);
}

/* ------------------------------------------------------------------ */
/* Internal: validate open params                                     */
/* ------------------------------------------------------------------ */
static int validate_params(const DscOpenParams *p)
{
    if (!p) {
        return DSC_ERR_INVALID_ARG;
    }
    if (!p->elf_path || p->elf_path[0] == '\0') {
        return DSC_ERR_INVALID_ARG;
    }
    if (!p->transport || p->transport[0] == '\0') {
        return DSC_ERR_INVALID_ARG;
    }
    if (!p->arch || p->arch[0] == '\0') {
        return DSC_ERR_INVALID_ARG;
    }
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Internal: copy transport config from open params                   */
/* ------------------------------------------------------------------ */
static DscTransportConfig make_transport_config(const DscOpenParams *p)
{
    DscTransportConfig cfg;
    memset(&cfg, 0, sizeof(cfg));
    cfg.host       = p->host;
    cfg.port       = p->port;
    cfg.device     = p->device;
    cfg.baudrate   = p->baudrate;
    cfg.shm_path   = p->shm_path;
    cfg.shm_size   = p->shm_size;
    cfg.timeout_ms = p->timeout_ms;
    return cfg;
}

/* ------------------------------------------------------------------ */
/* Internal: allocate and zero-init context                           */
/* ------------------------------------------------------------------ */
static DscContext *alloc_context(const char *elf_path)
{
    DscContext *ctx = calloc(1, sizeof(*ctx));
    if (!ctx) {
        return NULL;
    }
    ctx->elf_path = strdup(elf_path);
    if (!ctx->elf_path) {
        free(ctx);
        return NULL;
    }
    dsc_symtab_init(&ctx->symtab);
    ctx->last_error[0] = '\0';
    return ctx;
}

/* ------------------------------------------------------------------ */
/* Internal: open DWARF and load symbols                              */
/* ------------------------------------------------------------------ */
static int open_dwarf(DscContext *ctx)
{
    int err = 0;
    ctx->dwarf = dsc_dwarf_open(ctx->elf_path, &err);
    if (!ctx->dwarf) {
        set_error(ctx, "DWARF open failed: %s", DscStrerror(err));
        return err ? err : DSC_ERR_DWARF_INIT;
    }
    int rc = dsc_dwarf_load_symbols(ctx->dwarf, &ctx->symtab);
    if (rc < 0) {
        set_error(ctx, "symbol load failed: %s", DscStrerror(rc));
        return rc;
    }
    DSC_LOG_INFO("loaded %zu symbols from %s",
                 dsc_symtab_count(&ctx->symtab), ctx->elf_path);
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Internal: create and open transport                                */
/* ------------------------------------------------------------------ */
static int open_transport(DscContext *ctx, const DscOpenParams *p)
{
    DscTransportConfig cfg = make_transport_config(p);
    ctx->transport = DscTransportCreate(p->transport, &cfg);
    if (!ctx->transport) {
        set_error(ctx, "unknown transport: %s", p->transport);
        return DSC_ERR_TRANSPORT_OPEN;
    }
    int rc = DscTransportOpen(ctx->transport);
    if (rc < 0) {
        set_error(ctx, "transport open failed: %s", DscStrerror(rc));
        return rc;
    }
    DSC_LOG_INFO("transport '%s' opened", p->transport);
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Internal: create arch adapter                                      */
/* ------------------------------------------------------------------ */
static int create_arch(DscContext *ctx, const char *arch_name)
{
    DscArchConfig arch_cfg;
    memset(&arch_cfg, 0, sizeof(arch_cfg));
    ctx->arch = DscArchCreate(arch_name, &arch_cfg);
    if (!ctx->arch) {
        set_error(ctx, "unknown arch: %s", arch_name);
        return DSC_ERR_INVALID_ARG;
    }
    DSC_LOG_INFO("arch '%s' created", arch_name);
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Internal: create resolve cache                                     */
/* ------------------------------------------------------------------ */
static int create_cache(DscContext *ctx)
{
    ctx->cache = DscResolveCacheCreate(DSC_CACHE_CAPACITY);
    if (!ctx->cache) {
        set_error(ctx, "resolve cache allocation failed");
        return DSC_ERR_NOMEM;
    }
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Internal: tear down on partial open failure                        */
/* ------------------------------------------------------------------ */
static void cleanup_partial(DscContext *ctx)
{
    if (ctx->cache) {
        DscResolveCacheDestroy(ctx->cache);
    }
    if (ctx->transport) {
        DscTransportClose(ctx->transport);
        DscTransportDestroy(ctx->transport);
    }
    if (ctx->arch) {
        DscArchDestroy(ctx->arch);
    }
    if (ctx->dwarf) {
        dsc_dwarf_close(ctx->dwarf);
    }
    dsc_symtab_free(&ctx->symtab);
    free(ctx->elf_path);
    free(ctx);
}

/* ------------------------------------------------------------------ */
/* Public: DscOpen                                                   */
/* ------------------------------------------------------------------ */
DscContext *DscOpen(const DscOpenParams *params)
{
    if (validate_params(params) < 0) {
        DSC_LOG_ERROR("DscOpen: invalid params");
        return NULL;
    }

    /* 确保内置 arch 后端已注册 */
    DscArchRegisterBuiltins();

    DscContext *ctx = alloc_context(params->elf_path);
    if (!ctx) {
        DSC_LOG_ERROR("DscOpen: out of memory");
        return NULL;
    }

    if (open_dwarf(ctx) < 0) {
        goto fail;
    }
    if (create_arch(ctx, params->arch) < 0) {
        goto fail;
    }
    if (open_transport(ctx, params) < 0) {
        goto fail;
    }
    if (create_cache(ctx) < 0) {
        goto fail;
    }

    DSC_LOG_INFO("dsc session opened: %s", params->elf_path);
    return ctx;

fail:
    DSC_LOG_ERROR("DscOpen failed: %s", ctx->last_error);
    cleanup_partial(ctx);
    return NULL;
}

/* ------------------------------------------------------------------ */
/* Public: DscClose                                                  */
/* ------------------------------------------------------------------ */
void DscClose(DscContext *ctx)
{
    if (!ctx) {
        return;
    }
    DscResolveCacheDestroy(ctx->cache);
    DscTransportClose(ctx->transport);
    DscTransportDestroy(ctx->transport);
    DscArchDestroy(ctx->arch);
    dsc_dwarf_close(ctx->dwarf);
    dsc_symtab_free(&ctx->symtab);
    free(ctx->elf_path);
    free(ctx);
}

/* ------------------------------------------------------------------ */
/* Internal: resolve variable path (with caching)                     */
/* ------------------------------------------------------------------ */
static int resolve_var(DscContext *ctx, const char *var_path,
                       DscResolved *resolved)
{
    int rc = DscResolveCached(ctx->cache, &ctx->symtab, ctx->arch,
                                var_path, resolved);
    if (rc < 0) {
        set_error(ctx, "resolve '%s': %s", var_path, DscStrerror(rc));
    }
    return rc;
}

/* ------------------------------------------------------------------ */
/* Internal: read raw bytes for a resolved variable                   */
/* ------------------------------------------------------------------ */
static int read_var_bytes(DscContext *ctx, const DscResolved *resolved,
                          void *buf, UINT32 buf_len)
{
    if (resolved->size > buf_len) {
        set_error(ctx, "variable too large: %zu bytes", resolved->size);
        return DSC_ERR_INVALID_ARG;
    }
    int rc = DscMemRead(ctx->transport, ctx->arch,
                          resolved->addr, buf, resolved->size);
    if (rc < 0) {
        set_error(ctx, "mem_read @0x%llx: %s",
                  (unsigned long long)resolved->addr, DscStrerror(rc));
    }
    return rc;
}

/* ------------------------------------------------------------------ */
/* Internal: format resolved variable into output buffer              */
/* ------------------------------------------------------------------ */
static int format_var(DscContext *ctx,
                      const void *data, UINT32 data_len,
                      const dsc_type_t *type,
                      const DscFormatOpts *opts,
                      char *out, UINT32 out_len)
{
    char *formatted = DscFormatStr(data, data_len, type, opts);
    if (!formatted) {
        set_error(ctx, "format failed");
        return DSC_ERR_NOMEM;
    }
    UINT32 needed = strlen(formatted);
    if (needed >= out_len) {
        set_error(ctx, "output buffer too small: need %zu, have %zu",
                  needed + 1, out_len);
        free(formatted);
        return DSC_ERR_INVALID_ARG;
    }
    memcpy(out, formatted, needed + 1);
    free(formatted);
    return DSC_OK;
}

/* Max stack buffer for variable reads */
#define DSC_VAR_STACK_BUF 4096

/* ------------------------------------------------------------------ */
/* Internal: read + format core (shared by read_var and read_var_ex)  */
/* ------------------------------------------------------------------ */
static int read_var_core(DscContext *ctx, const char *var_path,
                         const DscFormatOpts *opts,
                         char *out, UINT32 out_len)
{
    DscResolved resolved;
    DSC_TRY(resolve_var(ctx, var_path, &resolved));

    /* Use stack buffer for small vars, heap for large */
    UINT8 stack_buf[DSC_VAR_STACK_BUF];
    void *data = stack_buf;
    if (resolved.size > DSC_VAR_STACK_BUF) {
        data = malloc(resolved.size);
        if (!data) {
            set_error(ctx, "alloc %zu bytes for var read", resolved.size);
            return DSC_ERR_NOMEM;
        }
    }

    int rc = read_var_bytes(ctx, &resolved, data, resolved.size);
    if (rc == DSC_OK) {
        rc = format_var(ctx, data, resolved.size, resolved.type,
                        opts, out, out_len);
    }

    if (data != stack_buf) {
        free(data);
    }
    return rc;
}

/* ------------------------------------------------------------------ */
/* Public: DscReadVar (Layer 0 — zero config)                       */
/* ------------------------------------------------------------------ */
int DscReadVar(DscContext *ctx, const char *var_path,
                 char *out, UINT32 out_len)
{
    if (!ctx || !var_path || !out || out_len == 0) {
        return DSC_ERR_INVALID_ARG;
    }
    return read_var_core(ctx, var_path, NULL, out, out_len);
}

/* ------------------------------------------------------------------ */
/* Public: DscReadVarEx (Layer 1 — custom format)                  */
/* ------------------------------------------------------------------ */
int DscReadVarEx(DscContext *ctx, const char *var_path,
                    const DscFormatOpts *opts,
                    char *out, UINT32 out_len)
{
    if (!ctx || !var_path || !out || out_len == 0) {
        return DSC_ERR_INVALID_ARG;
    }
    return read_var_core(ctx, var_path, opts, out, out_len);
}

/* ------------------------------------------------------------------ */
/* Public: DscReadMem                                               */
/* ------------------------------------------------------------------ */
int DscReadMem(DscContext *ctx, UINT64 addr,
                 void *buf, UINT32 len)
{
    if (!ctx || !buf || len == 0) {
        return DSC_ERR_INVALID_ARG;
    }
    int rc = DscMemRead(ctx->transport, ctx->arch, addr, buf, len);
    if (rc < 0) {
        set_error(ctx, "read_mem @0x%llx len=%zu: %s",
                  (unsigned long long)addr, len, DscStrerror(rc));
    }
    return rc;
}

/* ------------------------------------------------------------------ */
/* Public: DscWriteMem                                              */
/* ------------------------------------------------------------------ */
int DscWriteMem(DscContext *ctx, UINT64 addr,
                  const void *buf, UINT32 len)
{
    if (!ctx || !buf || len == 0) {
        return DSC_ERR_INVALID_ARG;
    }
    int rc = DscMemWrite(ctx->transport, ctx->arch, addr, buf, len);
    if (rc < 0) {
        set_error(ctx, "write_mem @0x%llx len=%zu: %s",
                  (unsigned long long)addr, len, DscStrerror(rc));
    }
    return rc;
}

/* ------------------------------------------------------------------ */
/* Public: DscLastError                                             */
/* ------------------------------------------------------------------ */
const char *DscLastError(const DscContext *ctx)
{
    if (!ctx) {
        return "NULL context";
    }
    return ctx->last_error;
}

/* ------------------------------------------------------------------ */
/* Internal: close DWARF and clear symbol table (for reload)          */
/* ------------------------------------------------------------------ */
static void close_dwarf(DscContext *ctx)
{
    if (ctx->dwarf) {
        dsc_dwarf_close(ctx->dwarf);
        ctx->dwarf = NULL;
    }
    dsc_symtab_free(&ctx->symtab);
    dsc_symtab_init(&ctx->symtab);
}

/* ------------------------------------------------------------------ */
/* Public: DscReload                                                 */
/* ------------------------------------------------------------------ */
int DscExecCmd(DscContext *ctx, const char *cmd,
               char *resp, UINT32 resp_len)
{
    if (!ctx || !cmd || !resp || resp_len == 0) {
        return DSC_ERR_INVALID_ARG;
    }
    int rc = DscTransportExecCmd(ctx->transport, cmd, resp, resp_len);
    if (rc < 0) {
        set_error(ctx, "exec_cmd '%s': %s", cmd, DscStrerror(rc));
    }
    return rc;
}

/* ------------------------------------------------------------------ */
/* Public: DscReload                                                 */
/* ------------------------------------------------------------------ */
int DscReload(DscContext *ctx)
{
    if (!ctx) {
        return DSC_ERR_INVALID_ARG;
    }
    DSC_LOG_INFO("reloading ELF: %s", ctx->elf_path);

    /* Close old DWARF data */
    close_dwarf(ctx);

    /* Invalidate resolve cache */
    DscResolveCacheInvalidate(ctx->cache);

    /* Reopen and reload */
    int rc = open_dwarf(ctx);
    if (rc < 0) {
        DSC_LOG_ERROR("reload failed: %s", ctx->last_error);
    } else {
        DSC_LOG_INFO("reload complete: %zu symbols",
                     dsc_symtab_count(&ctx->symtab));
    }
    return rc;
}
