#ifndef SUT_IO_H
#define SUT_IO_H

#include "sut_types.h"

/* 原框架 HAL，由平台实现 */
extern ERRNO_T HW_MemWrite(UINT32 addr, const void *pBuf, UINT32 len);
extern ERRNO_T HW_MemRead (UINT32 addr, void *pBuf, UINT32 len);
extern ERRNO_T HW_MsgSend (UINT32 chan, const void *pBuf, UINT32 len);
extern ERRNO_T HW_MsgRecv (UINT32 chan, void *pBuf, UINT32 *pLen, INT32 tmoMs);

/* SUT 对外 API */
ERRNO_T SUT_MemWrite  (UINT32 addr, const void *pBuf, UINT32 len);
ERRNO_T SUT_MemTrigger(UINT32 reg,  UINT32 val);
ERRNO_T SUT_MemRead   (UINT32 addr, void *pBuf, UINT32 len);
ERRNO_T SUT_MemWait   (UINT32 reg,  UINT32 mask, UINT32 val, INT32 tmoMs);
ERRNO_T SUT_MsgSend   (UINT32 chan, const void *pBuf, UINT32 len);
ERRNO_T SUT_MsgRecv   (UINT32 chan, void *pBuf, UINT32 *pLen, INT32 tmoMs);

#endif
