#include "sut.h"
#include "smoke_internal.h"
#include "smoke_regs.h"
#include <stdio.h>
#include <string.h>

/* 满足链接：框架要求外部提供的符号 */
static ERRNO_T SmokeDummyCase(void) { return OK; }
const SutCaseStru g_sutCaseTable[] = {
    { 1, "smoke_dummy", SmokeDummyCase },
};
const UINT32 g_sutCaseCount = (UINT32)(sizeof(g_sutCaseTable) / sizeof(g_sutCaseTable[0]));

bool g_bugCheckLogEnable = false;

typedef ERRNO_T (*SmokeTestFn)(void);

typedef struct {
    const char  *pName;
    SmokeTestFn  pFn;
    bool         expectTimeout;
} SmokeTestEntryStru;

static void SmokeClearStatus(void)
{
    UINT32 zero = (UINT32)SMOKE_STATUS_CLEAR;
    (void)SUT_MemWrite((UINT32)SMOKE_REG_STATUS, &zero, (UINT32)sizeof(zero));
}

static ERRNO_T SmokeT1MemRwBasic(void)
{
    UINT8 src[SMOKE_DATA_LEN];
    UINT8 dst[SMOKE_DATA_LEN];
    for (UINT32 i = 0; i < (UINT32)SMOKE_DATA_LEN; i++) {
        src[i] = (UINT8)(i + (UINT8)SMOKE_STIM_BYTE_OFFSET);
    }
    (void)SUT_MemWrite((UINT32)SMOKE_DATA_ADDR, src, (UINT32)SMOKE_DATA_LEN);
    (void)SUT_MemRead ((UINT32)SMOKE_DATA_ADDR, dst, (UINT32)SMOKE_DATA_LEN);
    return (memcmp(src, dst, (size_t)SMOKE_DATA_LEN) == 0) ? OK : ERROR;
}

static ERRNO_T SmokeT2MemTriggerHappy(void)
{
    UINT8 stim[SMOKE_DATA_LEN];
    UINT8 expect[SMOKE_DATA_LEN];
    UINT8 got[SMOKE_DATA_LEN];
    for (UINT32 i = 0; i < (UINT32)SMOKE_DATA_LEN; i++) {
        stim[i]   = (UINT8)i;
        expect[i] = (UINT8)(stim[i] ^ (UINT8)SMOKE_PROCESS_XOR_KEY);
    }

    SmokeClearStatus();
    (void)SUT_MemWrite  ((UINT32)SMOKE_DATA_ADDR,    stim, (UINT32)SMOKE_DATA_LEN);
    (void)SUT_MemTrigger((UINT32)SMOKE_REG_DOORBELL, (UINT32)SMOKE_DOORBELL_FIRE);

    ERRNO_T rc = SUT_MemWait((UINT32)SMOKE_REG_STATUS,
                             (UINT32)SMOKE_STATUS_DONE_MASK,
                             (UINT32)SMOKE_STATUS_DONE,
                             (INT32)SMOKE_WAIT_HAPPY_TMO_MS);
    if (rc != OK) {
        return ERROR;
    }
    (void)SUT_MemRead((UINT32)SMOKE_RESULT_ADDR, got, (UINT32)SMOKE_DATA_LEN);
    return (memcmp(got, expect, (size_t)SMOKE_DATA_LEN) == 0) ? OK : ERROR;
}

static ERRNO_T SmokeT3MemWaitTimeout(void)
{
    SMOKE_FakeFpgaStop();
    SmokeClearStatus();
    ERRNO_T rc = SUT_MemWait((UINT32)SMOKE_REG_STATUS,
                             (UINT32)SMOKE_STATUS_DONE_MASK,
                             (UINT32)SMOKE_STATUS_DONE,
                             (INT32)SMOKE_WAIT_TIMEOUT_TMO_MS);
    SMOKE_FakeFpgaStart();
    return (rc == ERROR) ? OK : ERROR;
}

static ERRNO_T SmokeT4RecSeqMonotonic(void)
{
    for (UINT32 i = 0; i < (UINT32)SMOKE_REC_SEQ_ROUNDS; i++) {
        if (SmokeT2MemTriggerHappy() != OK) {
            return ERROR;
        }
    }
    return OK;
}

static ERRNO_T SmokeT5RecLargePayload(void)
{
    UINT8 buf[SMOKE_LARGE_PAYLOAD_LEN];
    for (UINT32 i = 0; i < (UINT32)SMOKE_LARGE_PAYLOAD_LEN; i++) {
        buf[i] = (UINT8)i;
    }
    (void)SUT_MemWrite((UINT32)SMOKE_DATA_ADDR, buf, (UINT32)SMOKE_LARGE_PAYLOAD_LEN);
    return OK;
}

static ERRNO_T SmokeT6MsgEcho(void)
{
    UINT8  req [SMOKE_MSG_ECHO_LEN];
    UINT8  resp[SMOKE_MSG_ECHO_LEN];
    UINT32 respLen = (UINT32)sizeof(resp);

    for (UINT32 i = 0; i < (UINT32)SMOKE_MSG_ECHO_LEN; i++) {
        req[i] = (UINT8)(i * (UINT8)SMOKE_MSG_REQ_STEP);
    }

    (void)SUT_MsgSend((UINT32)SMOKE_MSG_CHAN, req, (UINT32)SMOKE_MSG_ECHO_LEN);
    ERRNO_T rc = SUT_MsgRecv((UINT32)SMOKE_MSG_CHAN, resp, &respLen,
                             (INT32)SMOKE_WAIT_HAPPY_TMO_MS);
    if (rc != OK) {
        return ERROR;
    }
    if (respLen != (UINT32)SMOKE_MSG_ECHO_LEN) {
        return ERROR;
    }
    for (UINT32 i = 0; i < (UINT32)SMOKE_MSG_ECHO_LEN; i++) {
        if (resp[i] != (UINT8)(req[i] ^ (UINT8)SMOKE_PROCESS_XOR_KEY)) {
            return ERROR;
        }
    }
    return OK;
}

static ERRNO_T SmokeT7CaseRegistry(void)
{
    const SutCaseStru *pCase = SUT_CaseFindByName("smoke_dummy");
    if (pCase == NULL) {
        return ERROR;
    }
    return SUT_CaseRun(pCase);
}

/* dut_dbg 集成测试（实现见 smoke_dut_dbg.c）*/
extern ERRNO_T SMOKE_DutDbgT1Handshake(void);
extern ERRNO_T SMOKE_DutDbgT2VarRw(void);
extern ERRNO_T SMOKE_DutDbgT3CanaryHealthy(void);
extern ERRNO_T SMOKE_DutDbgT4CanaryCorrupt(void);
extern ERRNO_T SMOKE_DutDbgT5RttRoundtrip(void);
extern ERRNO_T SMOKE_DutDbgT6RttWrap(void);
extern ERRNO_T SMOKE_DutDbgT7BeaconClean(void);
extern ERRNO_T SMOKE_DutDbgT8BeaconRescue(void);

int main(void)
{
    SutParamsStru params = {0};
    (void)strncpy(params.protoVersion, "smoke_v1", sizeof(params.protoVersion) - 1U);
    params.modelId   = 1;
    params.runSpec   = SUT_RUN_SPEC_FIRST;
    params.cmpMode   = SUT_CMP_MODE_STAGE;
    params.stageCmp  = SUT_STAGE_CMP_BASIC;
    params.hwSpec    = 0;
    params.powerMode = SUT_POWER_NORMAL;
    SUT_ParamsSet(&params);

    SMOKE_FakeFpgaStart();

    const SmokeTestEntryStru tests[] = {
        { "T1_MemRwBasic",      SmokeT1MemRwBasic,      false },
        { "T2_MemTriggerHappy", SmokeT2MemTriggerHappy, false },
        { "T3_MemWaitTimeout",  SmokeT3MemWaitTimeout,  true  },
        { "T4_RecSeqMonotonic", SmokeT4RecSeqMonotonic, false },
        { "T5_RecLargePayload", SmokeT5RecLargePayload, false },
        { "T6_MsgEcho",         SmokeT6MsgEcho,         false },
        { "T7_CaseRegistry",    SmokeT7CaseRegistry,    false },
        { "DBG_T1_Handshake",     SMOKE_DutDbgT1Handshake,     false },
        { "DBG_T2_VarRw",         SMOKE_DutDbgT2VarRw,         false },
        { "DBG_T3_CanaryHealthy", SMOKE_DutDbgT3CanaryHealthy, false },
        { "DBG_T4_CanaryCorrupt", SMOKE_DutDbgT4CanaryCorrupt, false },
        { "DBG_T5_RttRoundtrip",  SMOKE_DutDbgT5RttRoundtrip,  false },
        { "DBG_T6_RttWrap",       SMOKE_DutDbgT6RttWrap,       false },
        { "DBG_T7_BeaconClean",   SMOKE_DutDbgT7BeaconClean,   false },
        { "DBG_T8_BeaconRescue",  SMOKE_DutDbgT8BeaconRescue,  false },
    };
    UINT32 total = (UINT32)(sizeof(tests) / sizeof(tests[0]));
    UINT32 pass  = 0;

    for (UINT32 i = 0; i < total; i++) {
        (void)printf("\n--- %s ---\n", tests[i].pName);
        ERRNO_T rc = tests[i].pFn();
        bool ok = (rc == OK);
        (void)printf("[TEST] %s %s%s\n",
                     ok ? "PASS" : "FAIL",
                     tests[i].pName,
                     tests[i].expectTimeout ? " (expected timeout)" : "");
        if (ok) {
            pass++;
        }
    }

    SMOKE_FakeFpgaStop();
    (void)printf("\nSummary: %u/%u PASS\n", pass, total);
    return (pass == total) ? 0 : 1;
}
