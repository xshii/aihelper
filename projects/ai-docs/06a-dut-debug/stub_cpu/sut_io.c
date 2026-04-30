#include "sut_io.h"
#include "sut_rec.h"
#include "sut_platform.h"
#include "sut_config.h"
#include "bug_check.h"

enum {
    SUT_WAIT_MIN_POLLS = 1,
    SUT_US_PER_MS      = 1000,
};

ERRNO_T SUT_MemWrite(UINT32 addr, const void *pBuf, UINT32 len)
{
    BUG_RET_VAL(pBuf == NULL && len > 0U, ERROR);
    ERRNO_T rc = HW_MemWrite(addr, pBuf, len);
    SUT_REC(SUT_OP_MW, addr, pBuf, len);
    return rc;
}

ERRNO_T SUT_MemTrigger(UINT32 reg, UINT32 val)
{
    UINT32 localVal = val;
    ERRNO_T rc = HW_MemWrite(reg, &localVal, (UINT32)sizeof(localVal));
    SUT_REC(SUT_OP_MT, reg, &localVal, (UINT32)sizeof(localVal));
    return rc;
}

ERRNO_T SUT_MemRead(UINT32 addr, void *pBuf, UINT32 len)
{
    BUG_RET_VAL(pBuf == NULL && len > 0U, ERROR);
    ERRNO_T rc = HW_MemRead(addr, pBuf, len);
    SUT_REC(SUT_OP_MR, addr, pBuf, len);
    return rc;
}

ERRNO_T SUT_MemWait(UINT32 reg, UINT32 mask, UINT32 val, INT32 tmoMs)
{
    UINT32 maxPolls = (tmoMs <= 0)
                      ? (UINT32)SUT_WAIT_MIN_POLLS
                      : ((UINT32)tmoMs * (UINT32)SUT_US_PER_MS) / SUT_WAIT_POLL_US;
    BUG_RET_VAL(maxPolls == 0U, ERROR);

    UINT32 expected = val;
    SUT_REC(SUT_OP_WAIT, reg, &expected, (UINT32)sizeof(expected));

    UINT32 cur = 0U;
    for (UINT32 i = 0; i < maxPolls; i++) {
        (void)HW_MemRead(reg, &cur, (UINT32)sizeof(cur));
        if ((cur & mask) == val) {
            SUT_REC(SUT_OP_DONE, reg, &cur, (UINT32)sizeof(cur));
            return OK;
        }
        SUT_DelayUs(SUT_WAIT_POLL_US);
    }

    SUT_REC(SUT_OP_TMOUT, reg, &cur, (UINT32)sizeof(cur));
    return ERROR;
}

ERRNO_T SUT_MsgSend(UINT32 chan, const void *pBuf, UINT32 len)
{
    BUG_RET_VAL(pBuf == NULL && len > 0U, ERROR);
    ERRNO_T rc = HW_MsgSend(chan, pBuf, len);
    SUT_REC(SUT_OP_SND, chan, pBuf, len);
    return rc;
}

ERRNO_T SUT_MsgRecv(UINT32 chan, void *pBuf, UINT32 *pLen, INT32 tmoMs)
{
    BUG_RET_VAL(pBuf == NULL, ERROR);
    BUG_RET_VAL(pLen == NULL, ERROR);
    ERRNO_T rc = HW_MsgRecv(chan, pBuf, pLen, tmoMs);
    if (rc == OK) {
        SUT_REC(SUT_OP_RCV, chan, pBuf, *pLen);
    }
    return rc;
}
