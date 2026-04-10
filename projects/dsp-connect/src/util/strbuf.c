/* PURPOSE: strbuf 实现
 * PATTERN: Append-only growable buffer with printf support
 * FOR: 弱 AI 参考如何做动态字符串拼接 */

#include "strbuf.h"
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <stdio.h>

static void ensure_cap(DscStrbuf *sb, UINT32 extra)
{
    UINT32 need = sb->len + extra + 1; /* +1 for '\0' */
    if (need <= sb->cap) {
        return;
    }

    UINT32 newcap = sb->cap * 2;
    if (newcap < need) {
        newcap = need;
    }
    if (newcap < 64) {
        newcap = 64;
    }

    sb->buf = realloc(sb->buf, newcap);
    sb->cap = newcap;
}

void DscStrbufInit(DscStrbuf *sb, UINT32 initial_cap)
{
    if (initial_cap < 64) {
        initial_cap = 64;
    }
    sb->buf = malloc(initial_cap);
    sb->buf[0] = '\0';
    sb->len = 0;
    sb->cap = initial_cap;
}

void DscStrbufFree(DscStrbuf *sb)
{
    free(sb->buf);
    sb->buf = NULL;
    sb->len = 0;
    sb->cap = 0;
}

void DscStrbufAppend(DscStrbuf *sb, const char *str)
{
    UINT32 slen = strlen(str);
    ensure_cap(sb, slen);
    memcpy(sb->buf + sb->len, str, slen + 1);
    sb->len += slen;
}

void DscStrbufAppendn(DscStrbuf *sb, const char *str, UINT32 n)
{
    ensure_cap(sb, n);
    memcpy(sb->buf + sb->len, str, n);
    sb->len += n;
    sb->buf[sb->len] = '\0';
}

void DscStrbufAppendf(DscStrbuf *sb, const char *fmt, ...)
{
    va_list ap;

    /* First pass: measure */
    va_start(ap, fmt);
    int needed = vsnprintf(NULL, 0, fmt, ap);
    va_end(ap);

    if (needed <= 0) {
        return;
    }

    ensure_cap(sb, (UINT32)needed);

    /* Second pass: write */
    va_start(ap, fmt);
    vsnprintf(sb->buf + sb->len, (UINT32)needed + 1, fmt, ap);
    va_end(ap);

    sb->len += (UINT32)needed;
}

void DscStrbufIndent(DscStrbuf *sb, int depth)
{
    int spaces = depth * 2;
    ensure_cap(sb, (UINT32)spaces);
    for (int i = 0; i < spaces; i++) {
        sb->buf[sb->len++] = ' ';
    }
    sb->buf[sb->len] = '\0';
}

void DscStrbufReset(DscStrbuf *sb)
{
    sb->len = 0;
    if (sb->buf) {
        sb->buf[0] = '\0';
    }
}

const char *DscStrbufCstr(const DscStrbuf *sb)
{
    return sb->buf;
}
