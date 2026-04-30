/*
 * compare_buf.c — 机制 B 比数缓冲发布器（DUT 固件侧实现，详见 06b § 1.6.3）.
 *
 * 关键约束：
 *   - 顺序：先填描述符所有 4 个字段 → DUT_DSB → 递增 g_compareBufDebugCnt
 *   - 顺序颠倒会让桩 CPU 读到未初始化项；DUT_DSB 保证写顺序在弱序架构上不被重排
 *   - 第 (CAPACITY+1) 项溢出 → COMPARE_BUF_SetOverflowHandler 注册的钩子
 *
 * 嵌入摩擦：
 *   - 不假设地址范围，物理布局由平台链接脚本决定
 *   - 不强 extern 任何工程符号；DFX 接入走运行时注册函数（.so 友好）
 *   - g_compareBufDebugCnt / g_compareBufCompAddr 默认 64B 对齐
 */

#include "compare_buf.h"
#include "bug_check.h"

/* 64B 对齐：避免 DDR burst / cache line 撕裂。 */
#if defined(__GNUC__) || defined(__clang__)
#  define COMPARE_BUF_ALIGN_64  __attribute__((aligned(64)))
#else
#  define COMPARE_BUF_ALIGN_64
#endif

COMPARE_BUF_ALIGN_64 volatile UINT32           g_compareBufDebugCnt = 0u;
COMPARE_BUF_ALIGN_64 volatile CompareEntryStru g_compareBufCompAddr[COMPARE_BUF_CAPACITY];

/* 数据同步屏障 — 跨架构内建，编译器自选目标指令 */
#if defined(__GNUC__) || defined(__clang__)
#  define DUT_DSB()  __sync_synchronize()
#else
#  define DUT_DSB()
#endif

/* 溢出告警钩子 — 业务注册的回调；未注册时 NULL，溢出静默丢弃。 */
static CompareBufOverflowHandlerFn g_compareBufOverflowHandler = NULL;

void COMPARE_BUF_SetOverflowHandler(CompareBufOverflowHandlerFn handler)
{
    g_compareBufOverflowHandler = handler;
}

/* 与 Autotest 端 errors.py::ERR_COMPARE_BUF_OVERFLOW 对齐（0x4002）；
 * 0x4001 留给通用数据完整性 (CRC mismatch)。 */
#define COMPARE_BUF_ALARM_OVERFLOW   0x4002u

INT32 COMPARE_BUF_Publish(UINT16 tid, UINT16 cnt, const void *addr, UINT32 length)
{
    UINT32 i = g_compareBufDebugCnt;
    if (i >= COMPARE_BUF_CAPACITY) {
        if (g_compareBufOverflowHandler != NULL) {
            g_compareBufOverflowHandler(COMPARE_BUF_ALARM_OVERFLOW);
        }
        return ERROR;
    }
    /* 顺序 1：先填描述符全部字段 */
    g_compareBufCompAddr[i].tid    = tid;
    g_compareBufCompAddr[i].cnt    = cnt;
    g_compareBufCompAddr[i].length = length;
    g_compareBufCompAddr[i].addr   = (UINT64)(uintptr_t)addr;

    /* 顺序 2：屏障，确保上面的写在 g_compareBufDebugCnt 之前对桩 CPU 可见 */
    DUT_DSB();

    /* 顺序 3：原子递增（这里 32 位写本身原子；多核场景应换 atomic_fetch_add）*/
    g_compareBufDebugCnt = i + 1u;
    return OK;
}

bool COMPARE_BUF_Consumed(void)
{
    /* 桩 CPU 写 0 = 已消费；本侧只读 */
    return (g_compareBufDebugCnt == 0u);
}

INT32 COMPARE_BUF_SelfCheck(void)
{
    /* 8B 对齐校验 — 兜底捕获链接脚本异常定址。
     * 编译期 _Static_assert 已保证 sizeof/alignof，运行时只需查起始地址。 */
    BUG_RET_VAL(((uintptr_t)&g_compareBufDebugCnt) % 8u != 0u, ERROR);
    BUG_RET_VAL(((uintptr_t)&g_compareBufCompAddr[0]) % 8u != 0u, ERROR);
    return OK;
}
