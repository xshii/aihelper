#include "dut_dbg_target.h"
#include "bug_check.h"

/* DUT 嵌入物：不依赖 <string.h>。
 *
 * 嵌入式 freestanding 工具链常无 libc string；本文件提供局部 byte-loop
 * 实现替代 memset/memcpy/strlen。注意 GCC/clang 在 -O2 下可能识别这些
 * 循环并 emit memset/memcpy 调用 —— 嵌入工程如确实无 RT，需加
 * -fno-builtin-memset / -fno-builtin-memcpy 或自行提供 RT 实现。 */

static void dut_memzero(void *p, uint32_t n)
{
    uint8_t *q = (uint8_t *)p;
    for (uint32_t i = 0; i < n; i++) {
        q[i] = 0u;
    }
}

static void dut_memcopy(void *dst, const void *src, uint32_t n)
{
    uint8_t *d = (uint8_t *)dst;
    const uint8_t *s = (const uint8_t *)src;
    for (uint32_t i = 0; i < n; i++) {
        d[i] = s[i];
    }
}

static uint32_t dut_strnlen(const char *s, uint32_t maxlen)
{
    uint32_t i = 0u;
    while (i < maxlen && s[i] != '\0') {
        i++;
    }
    return i;
}

void DUT_DBG_TargetInit(DutDbgRegionStru *pRegion)
{
    BUG_RET(pRegion == NULL);
    dut_memzero(pRegion, (uint32_t)sizeof(*pRegion));
    pRegion->regionMagic = DUT_DBG_REGION_MAGIC;
    pRegion->regionSize  = (uint32_t)sizeof(*pRegion);

    /* RTT 控制块初始化 */
    dut_memcopy(pRegion->rtt.magic, DUT_RTT_MAGIC_STR,
                (uint32_t)sizeof(pRegion->rtt.magic));
    pRegion->rtt.bufSize = (uint32_t)DUT_RTT_BUF_SIZE;

    /* Canary 全部 arm */
    for (uint32_t i = 0; i < (uint32_t)DUT_CANARY_SLOTS; i++) {
        pRegion->canary.slot[i] = (uint32_t)DUT_CANARY_PATTERN;
    }

    /* Beacon magic 留空（无 crash 时 magic 不应匹配）*/
}

void DUT_DBG_TargetRttWrite(DutDbgRegionStru *pRegion,
                            const char *pStr, uint32_t len)
{
    BUG_RET(pRegion == NULL || pStr == NULL || len == 0U);

    DutRttCbStru *pCb = &pRegion->rtt;
    uint32_t wr   = pCb->wrOff;
    uint32_t rd   = pCb->rdOff;
    uint32_t size = pCb->bufSize;

    /* free = size - 1 - 已用；满则丢（非阻塞）*/
    uint32_t used = (wr >= rd) ? (wr - rd) : (size - rd + wr);
    uint32_t freeBytes = (size > 0U) ? (size - 1U - used) : 0U;
    if (len > freeBytes) {
        return;
    }

    for (uint32_t i = 0; i < len; i++) {
        pCb->buffer[(wr + i) % size] = (uint8_t)pStr[i];
    }
    /* 屏障：数据先落、wrOff 后翻 */
    __sync_synchronize();
    pCb->wrOff = (wr + len) % size;
}

void DUT_DBG_TargetBeaconWrite(DutDbgRegionStru *pRegion,
                               uint32_t cause, uint32_t pc,
                               const uint32_t regs[DUT_BEACON_REGS_NUM],
                               const char *pMsg,
                               const uint8_t *pStackTop, uint32_t stackLen,
                               uint64_t timestamp)
{
    BUG_RET(pRegion == NULL);

    DutBeaconStru *pB = &pRegion->beacon;
    pB->timestamp = timestamp;
    pB->cause     = cause;
    pB->pc        = pc;

    if (regs != NULL) {
        dut_memcopy(pB->regs, regs, (uint32_t)sizeof(pB->regs));
        /* RISC-V 约定：x1=ra, x2=sp */
        pB->ra = regs[1];
        pB->sp = regs[2];
    }

    if (pMsg != NULL) {
        uint32_t mlen = dut_strnlen(pMsg, (uint32_t)DUT_BEACON_MSG_LEN - 1U);
        dut_memcopy(pB->msg, pMsg, mlen);
        pB->msg[mlen] = 0U;
    }

    if (pStackTop != NULL && stackLen > 0U) {
        uint32_t dumpLen = stackLen;
        if (dumpLen > (uint32_t)DUT_BEACON_STACK_LEN) {
            dumpLen = (uint32_t)DUT_BEACON_STACK_LEN;
        }
        dut_memcopy(pB->stackDump, pStackTop, dumpLen);
    }

    /* 屏障：所有现场先写，magic 最后落 — 桩 CPU 看到 magic 即可信全部就绪 */
    __sync_synchronize();
    dut_memcopy(pB->magic, DUT_BEACON_MAGIC_STR, (uint32_t)sizeof(pB->magic));
}

void DUT_DBG_TargetCanaryArm(DutDbgRegionStru *pRegion, uint32_t slot)
{
    BUG_RET(pRegion == NULL || slot >= (uint32_t)DUT_CANARY_SLOTS);
    pRegion->canary.slot[slot] = (uint32_t)DUT_CANARY_PATTERN;
}

void DUT_DBG_TargetCanaryCorrupt(DutDbgRegionStru *pRegion, uint32_t slot)
{
    BUG_RET(pRegion == NULL || slot >= (uint32_t)DUT_CANARY_SLOTS);
    pRegion->canary.slot[slot] = 0xBADBADU;
}
