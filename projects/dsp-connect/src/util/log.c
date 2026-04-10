/* PURPOSE: 默认日志实现 — stderr 输出
 * PATTERN: 全局函数指针 + 默认实现
 * FOR: 弱 AI 参考如何做可替换的日志后端 */

#include <stdarg.h>
#include <time.h>

#include "log.h"

static const char *level_names[] = {"DEBUG", "INFO", "WARN", "ERROR"};

/* --- Global state --- */
DscLogLevel DscLogMinLevel = DSC_LOG_LEVEL_INFO;
DscLogFn DscLogImpl = DscLogDefault;

void DscLogSetHandler(DscLogFn fn)
{
    DscLogImpl = fn ? fn : DscLogDefault;
}

void DscLogSetLevel(DscLogLevel level)
{
    DscLogMinLevel = level;
}

void DscLogDefault(DscLogLevel level, const char *file,
                     int line, const char *fmt, ...)
{
    if (level < DscLogMinLevel) {
        return;
    }

    time_t now = time(NULL);
    struct tm *tm = localtime(&now);
    char timebuf[20];
    strftime(timebuf, sizeof(timebuf), "%H:%M:%S", tm);

    fprintf(stderr, "[%s][%-5s] %s:%d: ", timebuf, level_names[level], file, line);

    va_list ap;
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);

    fprintf(stderr, "\n");
}
