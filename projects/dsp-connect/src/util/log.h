/* PURPOSE: 最小化日志系统，编译期可控级别
 * PATTERN: 宏 → 函数指针，允许替换后端
 * FOR: 弱 AI 参考如何做可替换的日志层 */

#ifndef DSC_LOG_H
#define DSC_LOG_H

#include "types.h"
#include <stdio.h>

/* --- Log levels --- */
typedef enum {
    DSC_LOG_LEVEL_DEBUG = 0,
    DSC_LOG_LEVEL_INFO  = 1,
    DSC_LOG_LEVEL_WARN  = 2,
    DSC_LOG_LEVEL_ERROR = 3,
    DSC_LOG_LEVEL_NONE  = 4
} dsc_log_level_t;

/* --- Log callback signature --- */
typedef void (*dsc_log_fn)(dsc_log_level_t level, const char *file,
                           int line, const char *fmt, ...);

/* --- Global log function (replaceable) --- */
extern dsc_log_fn dsc_log_impl;
extern dsc_log_level_t dsc_log_min_level;

/* --- Public API --- */
void dsc_log_set_handler(dsc_log_fn fn);
void dsc_log_set_level(dsc_log_level_t level);
void dsc_log_default(dsc_log_level_t level, const char *file,
                     int line, const char *fmt, ...);

/* --- Convenience macros --- */
#define DSC_LOG_DEBUG(...) \
    do { if (dsc_log_min_level <= DSC_LOG_LEVEL_DEBUG) \
        dsc_log_impl(DSC_LOG_LEVEL_DEBUG, __FILE__, __LINE__, __VA_ARGS__); } while(0)

#define DSC_LOG_INFO(...) \
    do { if (dsc_log_min_level <= DSC_LOG_LEVEL_INFO) \
        dsc_log_impl(DSC_LOG_LEVEL_INFO, __FILE__, __LINE__, __VA_ARGS__); } while(0)

#define DSC_LOG_WARN(...) \
    do { if (dsc_log_min_level <= DSC_LOG_LEVEL_WARN) \
        dsc_log_impl(DSC_LOG_LEVEL_WARN, __FILE__, __LINE__, __VA_ARGS__); } while(0)

#define DSC_LOG_ERROR(...) \
    do { if (dsc_log_min_level <= DSC_LOG_LEVEL_ERROR) \
        dsc_log_impl(DSC_LOG_LEVEL_ERROR, __FILE__, __LINE__, __VA_ARGS__); } while(0)

#endif /* DSC_LOG_H */
