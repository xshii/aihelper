#ifndef SUT_REC_H
#define SUT_REC_H

#include "sut_types.h"
#include "sut_config.h"
#include "sut_ops.h"

#if SUT_RECORD
void SUT_RecEvent(SutOpEnum op, UINT32 key, const void *pData, UINT32 len);
#define SUT_REC(op, key, pData, len)  SUT_RecEvent((op), (key), (pData), (len))
#else
#define SUT_REC(op, key, pData, len)  ((void)0)
#endif

#endif
