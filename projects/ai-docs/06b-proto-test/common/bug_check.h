/*
 * bug_check.h — 工程级参数校验宏（mock 实现）.
 *
 * 嵌入工程已有同名头则直接复用；本头是 demo 兜底。
 * 行为简化：UNLIKELY 分支预测 + return；嵌入工程的真版本通常加日志路径
 * （PCIT printf / ESL_LOG_ERROR / BASE_LOG_ERROR），由 g_bugCheckLogEnable 控制。
 */

#ifndef BUG_CHECK_H
#define BUG_CHECK_H

#include <stdbool.h>

#ifndef UNLIKELY
#  if defined(__GNUC__) || defined(__clang__)
#    define UNLIKELY(x) __builtin_expect(!!(x), 0)
#  else
#    define UNLIKELY(x) (x)
#  endif
#endif

extern bool g_bugCheckLogEnable;

#define BUG_RET(cond)             do { if (UNLIKELY(cond)) { return; } } while (0)
#define BUG_RET_VAL(cond, val)    do { if (UNLIKELY(cond)) { return (val); } } while (0)
#define BUG_CONT(cond)            if (UNLIKELY(cond)) { continue; }
#define BUG_BREAK(cond)           if (UNLIKELY(cond)) { break; }

#endif /* BUG_CHECK_H */
