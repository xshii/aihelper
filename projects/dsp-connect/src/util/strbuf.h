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
} DscStrbuf;

/* Create / destroy */
void DscStrbufInit(DscStrbuf *sb, UINT32 initial_cap);
void DscStrbufFree(DscStrbuf *sb);

/* Append operations */
void DscStrbufAppend(DscStrbuf *sb, const char *str);
void DscStrbufAppendn(DscStrbuf *sb, const char *str, UINT32 n);
void DscStrbufAppendf(DscStrbuf *sb, const char *fmt, ...);

/* Indent helper: append N spaces */
void DscStrbufIndent(DscStrbuf *sb, int depth);

/* Reset (keep allocated memory) */
void DscStrbufReset(DscStrbuf *sb);

/* Get result (caller does NOT own the pointer — valid until next mutation or free) */
const char *DscStrbufCstr(const DscStrbuf *sb);

#endif /* DSC_STRBUF_H */
