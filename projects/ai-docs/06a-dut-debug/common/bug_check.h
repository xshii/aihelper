#ifndef BUG_CHECK_H
#define BUG_CHECK_H

/* 工程若已有 bug_check.h，删除本文件
 * 嵌入须知：本头只引 <stdbool.h>，无工程私有 typedef；嵌入工程
 * 在某 .c 中定义 ``bool g_bugCheckLogEnable = false;`` 即可链接。 */

#include <stdbool.h>

#ifndef UNLIKELY
#if defined(__GNUC__) || defined(__clang__)
#define UNLIKELY(x) __builtin_expect(!!(x), 0)
#else
#define UNLIKELY(x) (x)
#endif
#endif

extern bool g_bugCheckLogEnable;

#define BUG_RET(cond) \
    do { if (UNLIKELY(cond)) { return; } } while (0)

#define BUG_RET_VAL(cond, val) \
    do { if (UNLIKELY(cond)) { return (val); } } while (0)

#define BUG_CONT(cond) \
    if (UNLIKELY(cond)) { continue; }

#define BUG_BREAK(cond) \
    if (UNLIKELY(cond)) { break; }

#endif
