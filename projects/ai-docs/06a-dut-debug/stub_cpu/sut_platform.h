#ifndef SUT_PLATFORM_H
#define SUT_PLATFORM_H

#include "sut_types.h"
#include "sut_config.h"

/* 平台钩子：嵌入式替换这两个实现即可 */
void SUT_DelayUs(UINT32 us);
void dbginfo(const char *pFmt, ...);

#endif
