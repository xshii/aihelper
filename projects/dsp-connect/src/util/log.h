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
} DscLogLevel;

/* --- Log callback signature --- */
typedef void (*DscLogFn)(DscLogLevel level, const char *file,
                           int line, const char *fmt, ...);

/* --- Global log function (replaceable) --- */
extern DscLogFn DscLogImpl;
extern DscLogLevel DscLogMinLevel;

/* --- Public API --- */
void DscLogSetHandler(DscLogFn fn);
void DscLogSetLevel(DscLogLevel level);
void DscLogDefault(DscLogLevel level, const char *file,
                     int line, const char *fmt, ...);

/* --- Convenience macros --- */
#define DSC_LOG_DEBUG(...) \
    do { if (DscLogMinLevel <= DSC_LOG_LEVEL_DEBUG) \
        DscLogImpl(DSC_LOG_LEVEL_DEBUG, __FILE__, __LINE__, __VA_ARGS__); } while(0)

#define DSC_LOG_INFO(...) \
    do { if (DscLogMinLevel <= DSC_LOG_LEVEL_INFO) \
        DscLogImpl(DSC_LOG_LEVEL_INFO, __FILE__, __LINE__, __VA_ARGS__); } while(0)

#define DSC_LOG_WARN(...) \
    do { if (DscLogMinLevel <= DSC_LOG_LEVEL_WARN) \
        DscLogImpl(DSC_LOG_LEVEL_WARN, __FILE__, __LINE__, __VA_ARGS__); } while(0)

#define DSC_LOG_ERROR(...) \
    do { if (DscLogMinLevel <= DSC_LOG_LEVEL_ERROR) \
        DscLogImpl(DSC_LOG_LEVEL_ERROR, __FILE__, __LINE__, __VA_ARGS__); } while(0)

#endif /* DSC_LOG_H */
