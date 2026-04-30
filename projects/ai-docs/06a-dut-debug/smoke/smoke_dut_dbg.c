/* dut_dbg 集成 smoke 测试
 *
 * 复用 smoke_fake_hal 的 g_smokeFakeMem 同时模拟"被测内存"：
 *   - 被测侧：直接拿 fake mem 指针调 DUT_DBG_TargetXxx
 *   - 桩 CPU 侧：通过 SUT_MemRead/Write（fake hal 兜底）调 DUT_DBG_Xxx
 * 二者看到同一份内存，就和真实部署一致。
 */

#include "sut.h"
#include "smoke_internal.h"
#include "smoke_regs.h"
#include "dut_dbg.h"
#include "dut_dbg_target.h"
#include "dut_dbg_client.h"
#include <stdio.h>
#include <string.h>

static DutDbgRegionStru *DutDbgFakeRegion(void)
{
    return (DutDbgRegionStru *)SMOKE_FakeMemPtr((UINT32)SMOKE_DUT_DBG_OFFSET);
}

static ERRNO_T DbgSmokeSetup(void)
{
    DutDbgRegionStru *p = DutDbgFakeRegion();
    if (p == NULL) {
        return ERROR;
    }
    DUT_DBG_TargetInit(p);
    return DUT_DBG_ClientInit((UINT32)SMOKE_DUT_DBG_OFFSET);
}

/* T1：握手 —— 桩 CPU 应能读到 region magic + RTT magic */
ERRNO_T SMOKE_DutDbgT1Handshake(void)
{
    if (DbgSmokeSetup() != OK) {
        return ERROR;
    }
    return DUT_DBG_ClientHandshake();
}

/* T2：变量读写 —— 桩 CPU 直接读写被测内存中某地址 */
ERRNO_T SMOKE_DutDbgT2VarRw(void)
{
    if (DbgSmokeSetup() != OK) {
        return ERROR;
    }
    /* 选 fake mem 中一个独立位置当"被测全局变量"*/
    UINT32 varAddr = 0x3000U;
    UINT32 stim    = 0xCAFE5678U;
    UINT32 got     = 0U;

    if (DUT_DBG_VarWrite(varAddr, &stim, sizeof(stim)) != OK) {
        return ERROR;
    }
    if (DUT_DBG_VarRead(varAddr, &got, sizeof(got)) != OK) {
        return ERROR;
    }
    return (got == stim) ? OK : ERROR;
}

/* T3：金丝雀健康 —— init 后所有 slot 应为 pattern */
ERRNO_T SMOKE_DutDbgT3CanaryHealthy(void)
{
    if (DbgSmokeSetup() != OK) {
        return ERROR;
    }
    UINT32 badMask = 0xFFFFFFFFU;
    if (DUT_DBG_CanaryCheck(&badMask) != OK) {
        return ERROR;
    }
    return (badMask == 0U) ? OK : ERROR;
}

/* T4：金丝雀污染检测 —— 模拟栈溢出污染 slot 3，桩侧应检测出来 */
ERRNO_T SMOKE_DutDbgT4CanaryCorrupt(void)
{
    if (DbgSmokeSetup() != OK) {
        return ERROR;
    }
    DUT_DBG_TargetCanaryCorrupt(DutDbgFakeRegion(), 3U);

    UINT32 badMask = 0U;
    if (DUT_DBG_CanaryCheck(&badMask) != OK) {
        return ERROR;
    }
    return (badMask == (1U << 3U)) ? OK : ERROR;
}

/* T5：RTT 简单回环 —— 被测写一段日志，桩侧 pump 应一字不差读到 */
ERRNO_T SMOKE_DutDbgT5RttRoundtrip(void)
{
    if (DbgSmokeSetup() != OK) {
        return ERROR;
    }
    const char *pStim = "hello, dut_dbg!";
    UINT32 stimLen = (UINT32)strlen(pStim);

    DUT_DBG_TargetRttWrite(DutDbgFakeRegion(), pStim, stimLen);

    UINT8 outBuf[64];
    UINT32 got = 0U;
    if (DUT_DBG_RttPump(outBuf, (UINT32)sizeof(outBuf), &got) != OK) {
        return ERROR;
    }
    if (got != stimLen) {
        return ERROR;
    }
    return (memcmp(outBuf, pStim, stimLen) == 0) ? OK : ERROR;
}

/* T6：RTT 回绕 —— 多次写跨过 buffer 末尾，验证拆两段读不丢数据 */
ERRNO_T SMOKE_DutDbgT6RttWrap(void)
{
    if (DbgSmokeSetup() != OK) {
        return ERROR;
    }
    DutDbgRegionStru *p = DutDbgFakeRegion();
    UINT32 size = p->rtt.bufSize;

    /* 先写满 ~75% 让 wrOff 接近末尾 */
    UINT8 fillBuf[256];
    for (UINT32 i = 0; i < (UINT32)sizeof(fillBuf); i++) {
        fillBuf[i] = (UINT8)(i & 0xFFU);
    }
    UINT32 prefill = (size * 3U) / 4U;
    UINT32 written = 0U;
    while (written < prefill) {
        UINT32 chunk = (UINT32)sizeof(fillBuf);
        if (written + chunk > prefill) {
            chunk = prefill - written;
        }
        DUT_DBG_TargetRttWrite(p, (const char *)fillBuf, chunk);
        written += chunk;
    }

    /* 桩侧消费掉 prefill */
    UINT8 drain[512];
    UINT32 drained = 0U, total = 0U;
    do {
        if (DUT_DBG_RttPump(drain, (UINT32)sizeof(drain), &drained) != OK) {
            return ERROR;
        }
        total += drained;
    } while (drained > 0U);
    if (total != prefill) {
        return ERROR;
    }

    /* 此时 wrOff/rdOff 都已接近末尾。再写一段会跨越 size 边界 */
    const char *pStim = "WRAP_BOUNDARY_DATA_0123456789ABCDEF";
    UINT32 stimLen = (UINT32)strlen(pStim);
    DUT_DBG_TargetRttWrite(p, pStim, stimLen);

    UINT8 outBuf[64];
    UINT32 got = 0U;
    if (DUT_DBG_RttPump(outBuf, (UINT32)sizeof(outBuf), &got) != OK) {
        return ERROR;
    }
    if (got != stimLen) {
        return ERROR;
    }
    return (memcmp(outBuf, pStim, stimLen) == 0) ? OK : ERROR;
}

/* T7：Beacon 无 crash —— hasCrash 应返回 false */
ERRNO_T SMOKE_DutDbgT7BeaconClean(void)
{
    if (DbgSmokeSetup() != OK) {
        return ERROR;
    }
    DutBeaconStru beacon = {0};
    bool hasCrash = true;
    if (DUT_DBG_BeaconCheck(&beacon, &hasCrash) != OK) {
        return ERROR;
    }
    return (hasCrash == false) ? OK : ERROR;
}

/* T8：Beacon 救援 —— 模拟被测 trap 写 beacon，桩侧应正确读出现场 */
ERRNO_T SMOKE_DutDbgT8BeaconRescue(void)
{
    if (DbgSmokeSetup() != OK) {
        return ERROR;
    }
    DutDbgRegionStru *p = DutDbgFakeRegion();

    UINT32 fakeRegs[DUT_BEACON_REGS_NUM] = {0};
    fakeRegs[1] = 0x80001234U;        /* ra */
    fakeRegs[2] = 0x70008000U;        /* sp */
    fakeRegs[10] = 0xDEADBEEFU;       /* a0 */

    UINT8 fakeStack[64];
    for (UINT32 i = 0; i < (UINT32)sizeof(fakeStack); i++) {
        fakeStack[i] = (UINT8)(0xC0U + (i & 0x0FU));
    }

    DUT_DBG_TargetBeaconWrite(p,
        /* cause   */ 0x5U,           /* RISC-V load access fault */
        /* pc      */ 0x80009ABCU,
        /* regs    */ fakeRegs,
        /* msg     */ "panic: NULL deref in run_model",
        /* stack   */ fakeStack,
        /* stkLen  */ (UINT32)sizeof(fakeStack),
        /* time    */ 0x12345678U);

    DutBeaconStru got = {0};
    bool hasCrash = false;
    if (DUT_DBG_BeaconCheck(&got, &hasCrash) != OK) {
        return ERROR;
    }
    if (!hasCrash) {
        return ERROR;
    }
    if (got.cause != 0x5U)             { return ERROR; }
    if (got.pc    != 0x80009ABCU)      { return ERROR; }
    if (got.ra    != 0x80001234U)      { return ERROR; }
    if (got.sp    != 0x70008000U)      { return ERROR; }
    if (got.regs[10] != 0xDEADBEEFU)   { return ERROR; }
    if (memcmp(got.stackDump, fakeStack, sizeof(fakeStack)) != 0) {
        return ERROR;
    }
    if (strncmp((const char *)got.msg, "panic:", 6U) != 0) {
        return ERROR;
    }
    return OK;
}
