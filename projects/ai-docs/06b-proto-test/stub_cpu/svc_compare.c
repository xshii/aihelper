/*
 * svc_compare.c — 桩 CPU 侧机制 B 比数 svc（详见 06b § 1.6.4 / § 4.6）.
 *
 * 实现 SVC_COMPARE_PullBatch / SVC_COMPARE_Clear（在 mechanism_ops_t 表中绑定）。
 *
 * 风格：codestyle 工程命名；常量集中、无魔法字、所有外部依赖通过 extern 声明。
 */

#include "sut_types.h"
#include "compare_buf.h"        /* 复用 DUT 侧 CompareEntryStru / COMPARE_BUF_CAPACITY */

#define COMPARE_BATCH_MAX       COMPARE_BUF_CAPACITY

/* SoftDebug L6B SDK — 由其它文件提供（DUT 是 64 位地址空间）*/
extern INT32 L6B_SoftdebugRead (UINT64 addr, UINT32 n, void *out);
extern INT32 L6B_SoftdebugWrite(UINT64 addr, UINT32 n, const void *in);

/* 链接 map 中加载的 DUT 符号地址（image_activate 后由 svc_image 重载）*/
extern UINT64 g_svcCompareDutSymDebugCnt;     /* 对应 DUT 的 &g_compareBufDebugCnt   */
extern UINT64 g_svcCompareDutSymCompAddr;     /* 对应 DUT 的 &g_compareBufCompAddr[0]*/

/* 错误码段（与 errors.yaml 对齐）*/
#define ERR_OK                          0x0000
#define ERR_COMM_TIMEOUT                0x2001
#define ERR_DATA_INTEGRITY              0x4001
#define ERR_COMPARE_BUF_OVERFLOW        0x4002

/*
 * 拉一批比数描述符 + 数据。
 *   pOutEntries[0..N-1] = 描述符（按 1-based 1..N 顺序填入数组 0..N-1）
 *   pOutDataBuf[i]      = 第 i 条对应的数据（连续平铺，调用方按 length 切片）
 *
 * 返回：
 *    >= 0  实际项数 N
 *    < 0   错误码（取负）
 */
INT32 SVC_COMPARE_PullBatch(CompareEntryStru *pOutEntries,
                             UINT8            *pOutDataBuf,
                             UINT32            outDataBufSize,
                             UINT32           *pOutDataTotal)
{
    UINT32 n = 0u;
    INT32 rc;

    rc = L6B_SoftdebugRead(g_svcCompareDutSymDebugCnt, sizeof(UINT32), &n);
    if (rc != 0) { return -ERR_COMM_TIMEOUT; }
    if (n == 0u) { *pOutDataTotal = 0u; return 0; }
    if (n > COMPARE_BUF_CAPACITY) { return -ERR_COMPARE_BUF_OVERFLOW; }

    /* 一次性读全部描述符 — 减少 SoftDebug 往返次数 */
    rc = L6B_SoftdebugRead(g_svcCompareDutSymCompAddr,
                           n * sizeof(CompareEntryStru),
                           pOutEntries);
    if (rc != 0) { return -ERR_COMM_TIMEOUT; }

    /* 逐条按 entry.addr 拉数据 */
    UINT32 cursor = 0u;
    for (UINT32 i = 0u; i < n; ++i) {
        if (cursor + pOutEntries[i].length > outDataBufSize) {
            return -ERR_DATA_INTEGRITY;     /* 缓冲不够 */
        }
        rc = L6B_SoftdebugRead(pOutEntries[i].addr,
                               pOutEntries[i].length,
                               &pOutDataBuf[cursor]);
        if (rc != 0) { return -ERR_COMM_TIMEOUT; }
        cursor += pOutEntries[i].length;
    }
    *pOutDataTotal = cursor;
    return (INT32)n;
}

/*
 * 整体清零 g_compareBufDebugCnt（消费协议）。
 */
INT32 SVC_COMPARE_Clear(void)
{
    UINT32 zero = 0u;
    INT32 rc = L6B_SoftdebugWrite(g_svcCompareDutSymDebugCnt, sizeof(UINT32), &zero);
    return (rc == 0) ? ERR_OK : -ERR_COMM_TIMEOUT;
}
