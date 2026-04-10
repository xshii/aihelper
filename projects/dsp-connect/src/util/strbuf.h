/* PURPOSE: 可增长的字符串缓冲区，用于格式化输出
 * PATTERN: append-only buffer with printf support
 * FOR: 弱 AI 参考如何做动态字符串拼接 */

#ifndef DSC_STRBUF_H
#define DSC_STRBUF_H

#include "types.h"
#include <stddef.h>

typedef struct {
    char   *buf;
    UINT32  len;      /* current string length (excluding '\0') */
    UINT32  cap;      /* allocated capacity */
} dsc_strbuf_t;

/* Create / destroy */
void dsc_strbuf_init(dsc_strbuf_t *sb, UINT32 initial_cap);
void dsc_strbuf_free(dsc_strbuf_t *sb);

/* Append operations */
void dsc_strbuf_append(dsc_strbuf_t *sb, const char *str);
void dsc_strbuf_appendn(dsc_strbuf_t *sb, const char *str, UINT32 n);
void dsc_strbuf_appendf(dsc_strbuf_t *sb, const char *fmt, ...);

/* Indent helper: append N spaces */
void dsc_strbuf_indent(dsc_strbuf_t *sb, int depth);

/* Reset (keep allocated memory) */
void dsc_strbuf_reset(dsc_strbuf_t *sb);

/* Get result (caller does NOT own the pointer — valid until next mutation or free) */
const char *dsc_strbuf_cstr(const dsc_strbuf_t *sb);

#endif /* DSC_STRBUF_H */
