/*
 * compare_buf.c — 机制 B 比数缓冲发布器（DUT 固件侧实现，详见 06b § 1.6.3）.
 *
 * 关键约束：
 *   - 顺序：先填描述符所有 4 个字段 → __DSB → 递增 g_debugCnt
 *   - 顺序颠倒会让桩 CPU 读到未初始化项；__DSB 保证写顺序在弱序架构上不被重排
 *   - 第 201 项溢出 → dfx_raise_alarm()（详见 04 寄存器表）
 */

#include "compare_buf.h"

/*
 * Section 放置：嵌入式 ELF 用 .compare_buf；其它（如 macOS Mach-O 调试构建）
 * 留空，让默认 .data/.bss 走链接。真正部署时 .ld 决定固定地址。
 */
#if defined(__ELF__) && !defined(__APPLE__)
#  define COMPARE_BUF_SECTION  __attribute__((section(".compare_buf")))
#else
#  define COMPARE_BUF_SECTION  /* host build (e.g. macOS) — section ignored */
#endif

volatile uint32_t        g_debugCnt COMPARE_BUF_SECTION = 0u;
volatile compare_entry_t g_compAddr[COMPARE_BUF_CAPACITY] COMPARE_BUF_SECTION;

/* 数据同步屏障 — 弱序架构（ARM/RISC-V）上必需；x86 上是 NOP */
#if defined(__ARM_ARCH) || defined(__riscv)
#  define DUT_DSB()  __asm__ __volatile__("dsb" ::: "memory")
#else
#  define DUT_DSB()  __asm__ __volatile__("" ::: "memory")
#endif

/* DFX 告警接口（其它模块提供）*/
extern void dfx_raise_alarm(uint32_t alarm_code);
#define DFX_ALARM_COMPARE_BUF_OVERFLOW   0x4001u

int compare_buf_publish(uint16_t tid, uint16_t cnt, const void *addr, uint32_t length)
{
    uint32_t i = g_debugCnt;
    if (i >= COMPARE_BUF_CAPACITY) {
        dfx_raise_alarm(DFX_ALARM_COMPARE_BUF_OVERFLOW);
        return -1;
    }
    /* 顺序 1：先填描述符全部字段 */
    g_compAddr[i].tid    = tid;
    g_compAddr[i].cnt    = cnt;
    g_compAddr[i].length = length;
    g_compAddr[i].addr   = (void *)addr;

    /* 顺序 2：屏障，确保上面的写在 g_debugCnt 之前对桩 CPU 可见 */
    DUT_DSB();

    /* 顺序 3：原子递增（这里 32 位写本身原子；多核场景应换 atomic_fetch_add）*/
    g_debugCnt = i + 1u;
    return 0;
}

int compare_buf_consumed(void)
{
    /* 桩 CPU 写 0 = 已消费；本侧只读 */
    return (g_debugCnt == 0u) ? 1 : 0;
}
