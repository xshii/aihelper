#include "sut.h"
#include <stdio.h>
#include <stdarg.h>
#include <unistd.h>

/* 强符号覆盖 sut_platform.c 里的 weak 默认 */

void SUT_DelayUs(UINT32 us)
{
    (void)usleep(us);
}

void dbginfo(const char *pFmt, ...)
{
    va_list ap;
    va_start(ap, pFmt);
    (void)vprintf(pFmt, ap);
    va_end(ap);
}
