/* PURPOSE: 统一错误码定义 — 使用 X-macro 避免重复
 * PATTERN: X-macro — 一处定义，多处展开（枚举值、字符串表）
 * FOR: 弱 AI 参考如何做可维护的错误码系统 */

#ifndef DSC_ERRORS_H
#define DSC_ERRORS_H

/* X-macro: 每行 = X(枚举名, 错误码, 描述字符串)
 * 添加新错误只需加一行，枚举和字符串表自动同步 */
#define DSC_ERROR_TABLE(X) \
    X(DSC_OK,                  0, "success")                             \
    X(DSC_ERR_NOMEM,          -1, "out of memory")                       \
    X(DSC_ERR_INVALID_ARG,    -2, "invalid argument")                    \
    X(DSC_ERR_NOT_FOUND,      -3, "symbol not found")                    \
    X(DSC_ERR_ELF_OPEN,       -10, "failed to open ELF file")            \
    X(DSC_ERR_ELF_FORMAT,     -11, "invalid ELF format")                 \
    X(DSC_ERR_DWARF_INIT,     -12, "DWARF initialization failed")        \
    X(DSC_ERR_DWARF_PARSE,    -13, "DWARF parse error")                  \
    X(DSC_ERR_DWARF_NO_DEBUG, -14, "ELF has no debug info")              \
    X(DSC_ERR_TYPE_UNKNOWN,   -20, "unknown DWARF type")                 \
    X(DSC_ERR_TYPE_INCOMPLETE,-21, "incomplete type definition")          \
    X(DSC_ERR_RESOLVE_PATH,   -30, "cannot resolve member path")         \
    X(DSC_ERR_RESOLVE_INDEX,  -31, "array index out of bounds")          \
    X(DSC_ERR_TRANSPORT_OPEN, -40, "transport connection failed")         \
    X(DSC_ERR_TRANSPORT_IO,   -41, "transport I/O error")                \
    X(DSC_ERR_TRANSPORT_TIMEOUT,-42,"transport timeout")                  \
    X(DSC_ERR_MEM_READ,       -50, "memory read failed")                 \
    X(DSC_ERR_MEM_WRITE,      -51, "memory write failed")                \
    X(DSC_ERR_MEM_ALIGN,      -52, "unaligned memory access")            \
    X(DSC_ERR_ARCH_ADDR,      -60, "address translation error")

/* --- Expand to enum --- */
#define X_ENUM(name, code, desc) name = code,
typedef enum {
    DSC_ERROR_TABLE(X_ENUM)
} dsc_error_t;
#undef X_ENUM

/* --- API --- */
const char *dsc_strerror(int err);

#endif /* DSC_ERRORS_H */
