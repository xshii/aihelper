/* PURPOSE: Core glue layer — wires together dwarf, transport, arch, resolve,
 *          memory, and format into a single opaque context
 * PATTERN: Facade — one context struct holds all sub-system handles,
 *          public functions chain: resolve → mem_read → format
 * FOR: Weak AI to reference when building a top-level integration layer */

#include "dsc.h"
#include "dsc_errors.h"
#include "../dwarf/dwarf_parser.h"
#include "../dwarf/dwarf_symbols.h"
#include "../transport/transport.h"
#include "../transport/transport_factory.h"
#include "../arch/arch.h"
#include "../arch/arch_factory.h"
#include "../resolve/resolve.h"
#include "../resolve/resolve_cache.h"
#include "../memory/memory.h"
#include "../format/format.h"
#include "../util/log.h"

#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* ------------------------------------------------------------------ */
/* Error buffer size for last_error                                   */
/* ------------------------------------------------------------------ */
#define DSC_ERR_BUF_SIZE 512

/* Default resolve cache capacity */
#define DSC_CACHE_CAPACITY 1024

/* ------------------------------------------------------------------ */
/* Context struct — holds all sub-system handles                      */
/* ------------------------------------------------------------------ */
struct dsc_context_t {
    /* Sub-systems (all owned) */
    dsc_dwarf_t           *dwarf;
    dsc_symtab_t           symtab;
    dsc_transport_t       *transport;
    dsc_arch_t            *arch;
    dsc_resolve_cache_t   *cache;

    /* Config snapshot for reload */
    char                  *elf_path;

    /* Last error message */
    char                   last_error[DSC_ERR_BUF_SIZE];
};

/* ------------------------------------------------------------------ */
/* Internal: set last error message                                   */
/* ------------------------------------------------------------------ */
static void set_error(dsc_context_t *ctx, const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(ctx->last_error, DSC_ERR_BUF_SIZE, fmt, ap);
    va_end(ap);
}

/* ------------------------------------------------------------------ */
/* Internal: validate open params                                     */
/* ------------------------------------------------------------------ */
static int validate_params(const dsc_open_params_t *p)
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
static dsc_transport_config_t make_transport_config(const dsc_open_params_t *p)
{
    dsc_transport_config_t cfg;
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
static dsc_context_t *alloc_context(const char *elf_path)
{
    dsc_context_t *ctx = calloc(1, sizeof(*ctx));
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
static int open_dwarf(dsc_context_t *ctx)
{
    int err = 0;
    ctx->dwarf = dsc_dwarf_open(ctx->elf_path, &err);
    if (!ctx->dwarf) {
        set_error(ctx, "DWARF open failed: %s", dsc_strerror(err));
        return err ? err : DSC_ERR_DWARF_INIT;
    }
    int rc = dsc_dwarf_load_symbols(ctx->dwarf, &ctx->symtab);
    if (rc < 0) {
        set_error(ctx, "symbol load failed: %s", dsc_strerror(rc));
        return rc;
    }
    DSC_LOG_INFO("loaded %zu symbols from %s",
                 dsc_symtab_count(&ctx->symtab), ctx->elf_path);
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Internal: create and open transport                                */
/* ------------------------------------------------------------------ */
static int open_transport(dsc_context_t *ctx, const dsc_open_params_t *p)
{
    dsc_transport_config_t cfg = make_transport_config(p);
    ctx->transport = dsc_transport_create(p->transport, &cfg);
    if (!ctx->transport) {
        set_error(ctx, "unknown transport: %s", p->transport);
        return DSC_ERR_TRANSPORT_OPEN;
    }
    int rc = dsc_transport_open(ctx->transport);
    if (rc < 0) {
        set_error(ctx, "transport open failed: %s", dsc_strerror(rc));
        return rc;
    }
    DSC_LOG_INFO("transport '%s' opened", p->transport);
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Internal: create arch adapter                                      */
/* ------------------------------------------------------------------ */
static int create_arch(dsc_context_t *ctx, const char *arch_name)
{
    dsc_arch_config_t arch_cfg;
    memset(&arch_cfg, 0, sizeof(arch_cfg));
    ctx->arch = dsc_arch_create(arch_name, &arch_cfg);
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
static int create_cache(dsc_context_t *ctx)
{
    ctx->cache = dsc_resolve_cache_create(DSC_CACHE_CAPACITY);
    if (!ctx->cache) {
        set_error(ctx, "resolve cache allocation failed");
        return DSC_ERR_NOMEM;
    }
    return DSC_OK;
}

/* ------------------------------------------------------------------ */
/* Internal: tear down on partial open failure                        */
/* ------------------------------------------------------------------ */
static void cleanup_partial(dsc_context_t *ctx)
{
    if (ctx->cache) {
        dsc_resolve_cache_destroy(ctx->cache);
    }
    if (ctx->transport) {
        dsc_transport_close(ctx->transport);
        dsc_transport_destroy(ctx->transport);
    }
    if (ctx->arch) {
        dsc_arch_destroy(ctx->arch);
    }
    if (ctx->dwarf) {
        dsc_dwarf_close(ctx->dwarf);
    }
    dsc_symtab_free(&ctx->symtab);
    free(ctx->elf_path);
    free(ctx);
}

/* ------------------------------------------------------------------ */
/* Public: dsc_open                                                   */
/* ------------------------------------------------------------------ */
dsc_context_t *dsc_open(const dsc_open_params_t *params)
{
    if (validate_params(params) < 0) {
        DSC_LOG_ERROR("dsc_open: invalid params");
        return NULL;
    }

    dsc_context_t *ctx = alloc_context(params->elf_path);
    if (!ctx) {
        DSC_LOG_ERROR("dsc_open: out of memory");
        return NULL;
    }

    if (open_dwarf(ctx) < 0)                goto fail;
    if (create_arch(ctx, params->arch) < 0)  goto fail;
    if (open_transport(ctx, params) < 0)     goto fail;
    if (create_cache(ctx) < 0)               goto fail;

    DSC_LOG_INFO("dsc session opened: %s", params->elf_path);
    return ctx;

fail:
    DSC_LOG_ERROR("dsc_open failed: %s", ctx->last_error);
    cleanup_partial(ctx);
    return NULL;
}

/* ------------------------------------------------------------------ */
/* Public: dsc_close                                                  */
/* ------------------------------------------------------------------ */
void dsc_close(dsc_context_t *ctx)
{
    if (!ctx) {
        return;
    }
    dsc_resolve_cache_destroy(ctx->cache);
    dsc_transport_close(ctx->transport);
    dsc_transport_destroy(ctx->transport);
    dsc_arch_destroy(ctx->arch);
    dsc_dwarf_close(ctx->dwarf);
    dsc_symtab_free(&ctx->symtab);
    free(ctx->elf_path);
    free(ctx);
}

/* ------------------------------------------------------------------ */
/* Internal: resolve variable path (with caching)                     */
/* ------------------------------------------------------------------ */
static int resolve_var(dsc_context_t *ctx, const char *var_path,
                       dsc_resolved_t *resolved)
{
    int rc = dsc_resolve_cached(ctx->cache, &ctx->symtab, ctx->arch,
                                var_path, resolved);
    if (rc < 0) {
        set_error(ctx, "resolve '%s': %s", var_path, dsc_strerror(rc));
    }
    return rc;
}

/* ------------------------------------------------------------------ */
/* Internal: read raw bytes for a resolved variable                   */
/* ------------------------------------------------------------------ */
static int read_var_bytes(dsc_context_t *ctx, const dsc_resolved_t *resolved,
                          void *buf, size_t buf_len)
{
    if (resolved->size > buf_len) {
        set_error(ctx, "variable too large: %zu bytes", resolved->size);
        return DSC_ERR_INVALID_ARG;
    }
    int rc = dsc_mem_read(ctx->transport, ctx->arch,
                          resolved->addr, buf, resolved->size);
    if (rc < 0) {
        set_error(ctx, "mem_read @0x%llx: %s",
                  (unsigned long long)resolved->addr, dsc_strerror(rc));
    }
    return rc;
}

/* ------------------------------------------------------------------ */
/* Internal: format resolved variable into output buffer              */
/* ------------------------------------------------------------------ */
static int format_var(dsc_context_t *ctx,
                      const void *data, size_t data_len,
                      const dsc_type_t *type,
                      const dsc_format_opts_t *opts,
                      char *out, size_t out_len)
{
    char *formatted = dsc_format_str(data, data_len, type, opts);
    if (!formatted) {
        set_error(ctx, "format failed");
        return DSC_ERR_NOMEM;
    }
    size_t needed = strlen(formatted);
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
static int read_var_core(dsc_context_t *ctx, const char *var_path,
                         const dsc_format_opts_t *opts,
                         char *out, size_t out_len)
{
    dsc_resolved_t resolved;
    DSC_TRY(resolve_var(ctx, var_path, &resolved));

    /* Use stack buffer for small vars, heap for large */
    uint8_t stack_buf[DSC_VAR_STACK_BUF];
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
/* Public: dsc_read_var (Layer 0 — zero config)                       */
/* ------------------------------------------------------------------ */
int dsc_read_var(dsc_context_t *ctx, const char *var_path,
                 char *out, size_t out_len)
{
    if (!ctx || !var_path || !out || out_len == 0) {
        return DSC_ERR_INVALID_ARG;
    }
    return read_var_core(ctx, var_path, NULL, out, out_len);
}

/* ------------------------------------------------------------------ */
/* Public: dsc_read_var_ex (Layer 1 — custom format)                  */
/* ------------------------------------------------------------------ */
int dsc_read_var_ex(dsc_context_t *ctx, const char *var_path,
                    const dsc_format_opts_t *opts,
                    char *out, size_t out_len)
{
    if (!ctx || !var_path || !out || out_len == 0) {
        return DSC_ERR_INVALID_ARG;
    }
    return read_var_core(ctx, var_path, opts, out, out_len);
}

/* ------------------------------------------------------------------ */
/* Public: dsc_read_mem                                               */
/* ------------------------------------------------------------------ */
int dsc_read_mem(dsc_context_t *ctx, uint64_t addr,
                 void *buf, size_t len)
{
    if (!ctx || !buf || len == 0) {
        return DSC_ERR_INVALID_ARG;
    }
    int rc = dsc_mem_read(ctx->transport, ctx->arch, addr, buf, len);
    if (rc < 0) {
        set_error(ctx, "read_mem @0x%llx len=%zu: %s",
                  (unsigned long long)addr, len, dsc_strerror(rc));
    }
    return rc;
}

/* ------------------------------------------------------------------ */
/* Public: dsc_write_mem                                              */
/* ------------------------------------------------------------------ */
int dsc_write_mem(dsc_context_t *ctx, uint64_t addr,
                  const void *buf, size_t len)
{
    if (!ctx || !buf || len == 0) {
        return DSC_ERR_INVALID_ARG;
    }
    int rc = dsc_mem_write(ctx->transport, ctx->arch, addr, buf, len);
    if (rc < 0) {
        set_error(ctx, "write_mem @0x%llx len=%zu: %s",
                  (unsigned long long)addr, len, dsc_strerror(rc));
    }
    return rc;
}

/* ------------------------------------------------------------------ */
/* Public: dsc_last_error                                             */
/* ------------------------------------------------------------------ */
const char *dsc_last_error(const dsc_context_t *ctx)
{
    if (!ctx) {
        return "NULL context";
    }
    return ctx->last_error;
}

/* ------------------------------------------------------------------ */
/* Internal: close DWARF and clear symbol table (for reload)          */
/* ------------------------------------------------------------------ */
static void close_dwarf(dsc_context_t *ctx)
{
    if (ctx->dwarf) {
        dsc_dwarf_close(ctx->dwarf);
        ctx->dwarf = NULL;
    }
    dsc_symtab_free(&ctx->symtab);
    dsc_symtab_init(&ctx->symtab);
}

/* ------------------------------------------------------------------ */
/* Public: dsc_reload                                                 */
/* ------------------------------------------------------------------ */
int dsc_reload(dsc_context_t *ctx)
{
    if (!ctx) {
        return DSC_ERR_INVALID_ARG;
    }
    DSC_LOG_INFO("reloading ELF: %s", ctx->elf_path);

    /* Close old DWARF data */
    close_dwarf(ctx);

    /* Invalidate resolve cache */
    dsc_resolve_cache_invalidate(ctx->cache);

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
