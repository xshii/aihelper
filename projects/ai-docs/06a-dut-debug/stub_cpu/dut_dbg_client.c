#include "dut_dbg_client.h"
#include "sut_io.h"
#include "bug_check.h"
#include <string.h>

static UINT32 g_dutDbgRegionBase = 0U;
static bool   g_dutDbgClientInited = false;

ERRNO_T DUT_DBG_ClientInit(UINT32 regionBase)
{
    g_dutDbgRegionBase   = regionBase;
    g_dutDbgClientInited = true;
    return OK;
}

ERRNO_T DUT_DBG_ClientHandshake(void)
{
    BUG_RET_VAL(!g_dutDbgClientInited, ERROR);

    UINT32 magic = 0U;
    BUG_RET_VAL(SUT_MemRead(g_dutDbgRegionBase + (UINT32)DUT_DBG_OFF_REGION_MAGIC,
                            &magic, (UINT32)sizeof(magic)) != OK, ERROR);
    BUG_RET_VAL(magic != (UINT32)DUT_DBG_REGION_MAGIC, ERROR);

    char rttMagic[8] = {0};
    UINT32 rttMagicAddr = g_dutDbgRegionBase + (UINT32)DUT_DBG_OFF_RTT
                       + (UINT32)offsetof(DutRttCbStru, magic);
    BUG_RET_VAL(SUT_MemRead(rttMagicAddr, rttMagic, (UINT32)sizeof(rttMagic)) != OK, ERROR);
    BUG_RET_VAL(memcmp(rttMagic, DUT_RTT_MAGIC_STR, sizeof(rttMagic)) != 0, ERROR);

    return OK;
}

ERRNO_T DUT_DBG_RttPump(UINT8 *pOut, UINT32 cap, UINT32 *pOutLen)
{
    BUG_RET_VAL(!g_dutDbgClientInited, ERROR);
    BUG_RET_VAL(pOut == NULL || pOutLen == NULL, ERROR);
    *pOutLen = 0U;
    if (cap == 0U) {
        return OK;
    }

    UINT32 rttBase = g_dutDbgRegionBase + (UINT32)DUT_DBG_OFF_RTT;

    UINT32 wr = 0U, rd = 0U, size = 0U;
    BUG_RET_VAL(SUT_MemRead(rttBase + (UINT32)offsetof(DutRttCbStru, wrOff),
                            &wr, 4U) != OK, ERROR);
    BUG_RET_VAL(SUT_MemRead(rttBase + (UINT32)offsetof(DutRttCbStru, rdOff),
                            &rd, 4U) != OK, ERROR);
    BUG_RET_VAL(SUT_MemRead(rttBase + (UINT32)offsetof(DutRttCbStru, bufSize),
                            &size, 4U) != OK, ERROR);
    BUG_RET_VAL(size == 0U, ERROR);

    if (wr == rd) {
        return OK;          /* 没新数据 */
    }

    UINT32 avail = (wr > rd) ? (wr - rd) : (size - rd + wr);
    UINT32 take  = (avail < cap) ? avail : cap;
    UINT32 bufBase = rttBase + (UINT32)offsetof(DutRttCbStru, buffer);

    /* 处理回绕：可能需要分两段读 */
    if (rd + take <= size) {
        BUG_RET_VAL(SUT_MemRead(bufBase + rd, pOut, take) != OK, ERROR);
    } else {
        UINT32 first = size - rd;
        BUG_RET_VAL(SUT_MemRead(bufBase + rd, pOut, first) != OK, ERROR);
        BUG_RET_VAL(SUT_MemRead(bufBase, pOut + first, take - first) != OK, ERROR);
    }

    /* 推进 rdOff，让被测知道这段已被消费 */
    UINT32 newRd = (rd + take) % size;
    BUG_RET_VAL(SUT_MemWrite(rttBase + (UINT32)offsetof(DutRttCbStru, rdOff),
                             &newRd, 4U) != OK, ERROR);

    *pOutLen = take;
    return OK;
}

ERRNO_T DUT_DBG_BeaconCheck(DutBeaconStru *pBeacon, bool *pHasCrash)
{
    BUG_RET_VAL(!g_dutDbgClientInited, ERROR);
    BUG_RET_VAL(pBeacon == NULL || pHasCrash == NULL, ERROR);

    UINT32 base = g_dutDbgRegionBase + (UINT32)DUT_DBG_OFF_BEACON;
    char magic[8] = {0};
    BUG_RET_VAL(SUT_MemRead(base + (UINT32)offsetof(DutBeaconStru, magic),
                            magic, (UINT32)sizeof(magic)) != OK, ERROR);

    if (memcmp(magic, DUT_BEACON_MAGIC_STR, sizeof(magic)) != 0) {
        *pHasCrash = false;
        return OK;
    }

    /* 整段读出现场（magic 已确认） */
    BUG_RET_VAL(SUT_MemRead(base, pBeacon, (UINT32)sizeof(*pBeacon)) != OK, ERROR);
    *pHasCrash = true;
    return OK;
}

ERRNO_T DUT_DBG_CanaryCheck(UINT32 *pBadMask)
{
    BUG_RET_VAL(!g_dutDbgClientInited, ERROR);
    BUG_RET_VAL(pBadMask == NULL, ERROR);

    UINT32 base = g_dutDbgRegionBase + (UINT32)DUT_DBG_OFF_CANARY;
    UINT32 slots[DUT_CANARY_SLOTS];
    BUG_RET_VAL(SUT_MemRead(base, slots, (UINT32)sizeof(slots)) != OK, ERROR);

    UINT32 bad = 0U;
    for (UINT32 i = 0; i < (UINT32)DUT_CANARY_SLOTS; i++) {
        if (slots[i] != (UINT32)DUT_CANARY_PATTERN) {
            bad |= (1U << i);
        }
    }
    *pBadMask = bad;
    return OK;
}

ERRNO_T DUT_DBG_VarRead(UINT32 dutAddr, void *pOut, UINT32 size)
{
    BUG_RET_VAL(pOut == NULL || size == 0U, ERROR);
    return SUT_MemRead(dutAddr, pOut, size);
}

ERRNO_T DUT_DBG_VarWrite(UINT32 dutAddr, const void *pIn, UINT32 size)
{
    BUG_RET_VAL(pIn == NULL || size == 0U, ERROR);
    return SUT_MemWrite(dutAddr, pIn, size);
}
