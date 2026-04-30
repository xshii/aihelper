#ifndef SMOKE_INTERNAL_H
#define SMOKE_INTERNAL_H

#include "sut_types.h"
#include "bug_check.h"

void SMOKE_FakeFpgaStart(void);
void SMOKE_FakeFpgaStop(void);

bool SMOKE_FakeHalMsgPeekSend(UINT8 *pBuf, UINT32 *pLen);
void SMOKE_FakeHalMsgPostRecv(const UINT8 *pBuf, UINT32 len);

/* 暴露 fake mem 直接指针 —— 仅用于 dut_dbg smoke 模拟"被测侧"对 region 的直接访问。
 * 生产部署中被测侧本就是直接访问内存，这里用 fake mem 模拟该路径。 */
void *SMOKE_FakeMemPtr(UINT32 offset);

#endif
