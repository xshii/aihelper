#include "sut_platform.h"

/* weak 默认实现：真机/smoke 均由强符号覆盖 */

SUT_WEAK void SUT_DelayUs(UINT32 us)
{
    (void)us;
}

SUT_WEAK void dbginfo(const char *pFmt, ...)
{
    (void)pFmt;
}
