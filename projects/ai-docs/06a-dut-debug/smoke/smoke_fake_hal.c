#include "sut.h"
#include "smoke_internal.h"
#include "smoke_regs.h"
#include <string.h>
#include <pthread.h>

static UINT8 g_smokeFakeMem[SMOKE_FAKE_MEM_SIZE];
static pthread_mutex_t g_smokeFakeMemMtx = PTHREAD_MUTEX_INITIALIZER;

typedef struct {
    UINT8  data[SMOKE_MSG_MAX_LEN];
    UINT32 len;
    bool   valid;
} SmokeMsgSlotStru;

static SmokeMsgSlotStru g_smokeMsgToFpga;
static SmokeMsgSlotStru g_smokeMsgToCpu;
static pthread_mutex_t  g_smokeMsgMtx = PTHREAD_MUTEX_INITIALIZER;

ERRNO_T HW_MemWrite(UINT32 addr, const void *pBuf, UINT32 len)
{
    BUG_RET_VAL((UINT64)addr + len > (UINT64)SMOKE_FAKE_MEM_SIZE, ERROR);
    (void)pthread_mutex_lock(&g_smokeFakeMemMtx);
    (void)memcpy(g_smokeFakeMem + addr, pBuf, len);
    (void)pthread_mutex_unlock(&g_smokeFakeMemMtx);
    return OK;
}

ERRNO_T HW_MemRead(UINT32 addr, void *pBuf, UINT32 len)
{
    BUG_RET_VAL((UINT64)addr + len > (UINT64)SMOKE_FAKE_MEM_SIZE, ERROR);
    (void)pthread_mutex_lock(&g_smokeFakeMemMtx);
    (void)memcpy(pBuf, g_smokeFakeMem + addr, len);
    (void)pthread_mutex_unlock(&g_smokeFakeMemMtx);
    return OK;
}

ERRNO_T HW_MsgSend(UINT32 chan, const void *pBuf, UINT32 len)
{
    (void)chan;
    BUG_RET_VAL(len > (UINT32)SMOKE_MSG_MAX_LEN, ERROR);
    (void)pthread_mutex_lock(&g_smokeMsgMtx);
    (void)memcpy(g_smokeMsgToFpga.data, pBuf, len);
    g_smokeMsgToFpga.len   = len;
    g_smokeMsgToFpga.valid = true;
    (void)pthread_mutex_unlock(&g_smokeMsgMtx);
    return OK;
}

ERRNO_T HW_MsgRecv(UINT32 chan, void *pBuf, UINT32 *pLen, INT32 tmoMs)
{
    (void)chan;
    BUG_RET_VAL(pBuf == NULL, ERROR);
    BUG_RET_VAL(pLen == NULL, ERROR);

    INT32 tmoUs = (tmoMs <= 0) ? 0 : tmoMs * 1000;
    INT32 remaining = tmoUs;

    while (remaining >= 0) {
        (void)pthread_mutex_lock(&g_smokeMsgMtx);
        if (g_smokeMsgToCpu.valid) {
            UINT32 take = g_smokeMsgToCpu.len;
            if (take > *pLen) {
                take = *pLen;
            }
            (void)memcpy(pBuf, g_smokeMsgToCpu.data, take);
            *pLen = take;
            g_smokeMsgToCpu.valid = false;
            (void)pthread_mutex_unlock(&g_smokeMsgMtx);
            return OK;
        }
        (void)pthread_mutex_unlock(&g_smokeMsgMtx);
        SUT_DelayUs((UINT32)SMOKE_MSG_POLL_US);
        remaining -= (INT32)SMOKE_MSG_POLL_US;
        if (tmoUs == 0) {
            break;
        }
    }
    return ERROR;
}

bool SMOKE_FakeHalMsgPeekSend(UINT8 *pBuf, UINT32 *pLen)
{
    bool gotOne = false;
    (void)pthread_mutex_lock(&g_smokeMsgMtx);
    if (g_smokeMsgToFpga.valid) {
        (void)memcpy(pBuf, g_smokeMsgToFpga.data, g_smokeMsgToFpga.len);
        *pLen = g_smokeMsgToFpga.len;
        g_smokeMsgToFpga.valid = false;
        gotOne = true;
    }
    (void)pthread_mutex_unlock(&g_smokeMsgMtx);
    return gotOne;
}

void SMOKE_FakeHalMsgPostRecv(const UINT8 *pBuf, UINT32 len)
{
    BUG_RET(len > (UINT32)SMOKE_MSG_MAX_LEN);
    (void)pthread_mutex_lock(&g_smokeMsgMtx);
    (void)memcpy(g_smokeMsgToCpu.data, pBuf, len);
    g_smokeMsgToCpu.len   = len;
    g_smokeMsgToCpu.valid = true;
    (void)pthread_mutex_unlock(&g_smokeMsgMtx);
}

void *SMOKE_FakeMemPtr(UINT32 offset)
{
    if (offset >= (UINT32)SMOKE_FAKE_MEM_SIZE) {
        return NULL;
    }
    return (void *)(g_smokeFakeMem + offset);
}
