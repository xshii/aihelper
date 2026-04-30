#include "sut.h"
#include "smoke_internal.h"
#include "smoke_regs.h"
#include <pthread.h>
#include <stdatomic.h>

static atomic_bool g_smokeFakeFpgaRun;
static pthread_t   g_smokeFakeFpgaTid;

static void SmokeFakeFpgaProcessMemTrigger(void)
{
    UINT8 in[SMOKE_DATA_LEN];
    UINT8 out[SMOKE_DATA_LEN];
    (void)HW_MemRead((UINT32)SMOKE_DATA_ADDR, in, (UINT32)SMOKE_DATA_LEN);
    for (UINT32 i = 0; i < (UINT32)SMOKE_DATA_LEN; i++) {
        out[i] = (UINT8)(in[i] ^ (UINT8)SMOKE_PROCESS_XOR_KEY);
    }
    (void)HW_MemWrite((UINT32)SMOKE_RESULT_ADDR, out, (UINT32)SMOKE_DATA_LEN);

    UINT32 clear = (UINT32)SMOKE_DOORBELL_IDLE;
    UINT32 done  = (UINT32)SMOKE_STATUS_DONE;
    (void)HW_MemWrite((UINT32)SMOKE_REG_DOORBELL, &clear, (UINT32)sizeof(clear));
    (void)HW_MemWrite((UINT32)SMOKE_REG_STATUS,   &done,  (UINT32)sizeof(done));
}

static void SmokeFakeFpgaProcessMsg(void)
{
    UINT8 buf[SMOKE_MSG_MAX_LEN];
    UINT32 len = 0;
    if (!SMOKE_FakeHalMsgPeekSend(buf, &len)) {
        return;
    }
    for (UINT32 i = 0; i < len; i++) {
        buf[i] = (UINT8)(buf[i] ^ (UINT8)SMOKE_PROCESS_XOR_KEY);
    }
    SMOKE_FakeHalMsgPostRecv(buf, len);
}

static void *SmokeFakeFpgaLoop(void *pArg)
{
    (void)pArg;
    while (atomic_load(&g_smokeFakeFpgaRun)) {
        UINT32 db = 0;
        (void)HW_MemRead((UINT32)SMOKE_REG_DOORBELL, &db, (UINT32)sizeof(db));
        if ((db & (UINT32)SMOKE_DOORBELL_FIRE) != 0U) {
            SmokeFakeFpgaProcessMemTrigger();
        }
        SmokeFakeFpgaProcessMsg();
        SUT_DelayUs((UINT32)SMOKE_FAKE_FPGA_POLL_US);
    }
    return NULL;
}

void SMOKE_FakeFpgaStart(void)
{
    atomic_store(&g_smokeFakeFpgaRun, true);
    (void)pthread_create(&g_smokeFakeFpgaTid, NULL, SmokeFakeFpgaLoop, NULL);
}

void SMOKE_FakeFpgaStop(void)
{
    atomic_store(&g_smokeFakeFpgaRun, false);
    (void)pthread_join(g_smokeFakeFpgaTid, NULL);
}
