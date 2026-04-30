/*
 * compare_buf.h — 机制 B 比数协议 DUT 侧契约（详见 06b § 1.6）.
 *
 * 入口 / 全局符号：
 *   - g_compareBufDebugCnt              — 当前有效比数项数（UINT32；0 = 空）
 *   - g_compareBufCompAddr[CAPACITY]    — 比数描述符数组（CompareEntryStru[]）
 *
 * 协议要点：
 *   1) 生产顺序：先填 g_compareBufCompAddr[g_compareBufDebugCnt]，再以原子写递增 g_compareBufDebugCnt
 *   2) 消费侧（桩 CPU）整体写 0 → 固件视为已消费
 *   3) 第 (CAPACITY+1) 项溢出 → 调用 COMPARE_BUF_OnOverflow 钩子
 *   4) 同 tid 多次产出用 cnt 区分；GOLDEN 按 (tid, cnt) 二维索引
 *   5) g_compareBufDebugCnt / g_compareBufCompAddr 默认 64B 对齐（避免 DDR burst / cache line 撕裂）
 *
 * 平台职责（本 demo 不假设地址范围）：
 *   - 物理地址由平台链接脚本决定
 *   - 桩 CPU 通过 ELF 符号表 / .map 查询起址
 *
 * 嵌入选项（编译时 -D 覆盖）：
 *   COMPARE_BUF_CAPACITY  比数缓冲容量（默认 200）
 */

#ifndef DUT_COMPARE_BUF_H
#define DUT_COMPARE_BUF_H

#include "sut_types.h"

#ifndef COMPARE_BUF_CAPACITY
#  define COMPARE_BUF_CAPACITY  200u
#endif

/* 三方协议固定布局（DUT / 桩 CPU svc_compare.c / Python protocol.memory.CompareEntry 等价）：
 *
 *   offset  size  field
 *   ────────────────────────
 *     0      2    tid     (UINT16, 自然 2B 对齐)
 *     2      2    cnt     (UINT16, 自然 2B 对齐)
 *     4      4    length  (UINT32, 自然 4B 对齐)
 *     8      8    addr    (UINT64, 自然 8B 对齐) — 64 位 DUT 地址空间
 *   ────────────────────────
 *   total = 16 字节（编译器零 padding，且 alignof = 8） */
typedef struct {
    UINT16 tid;         /* 张量 / 阶段 ID */
    UINT16 cnt;         /* 同一 tid 的第几次产出 */
    UINT32 length;      /* 数据字节数 */
    UINT64 addr;        /* 数据起始地址（64 位 DUT 内存空间）*/
} CompareEntryStru;

_Static_assert(sizeof(CompareEntryStru) == 16,
               "CompareEntryStru must be exactly 16B (三方协议固定长度)");
_Static_assert(_Alignof(CompareEntryStru) >= 8,
               "CompareEntryStru must be 8B-aligned (UINT64 addr)");

extern volatile UINT32           g_compareBufDebugCnt;
extern volatile CompareEntryStru g_compareBufCompAddr[COMPARE_BUF_CAPACITY];

/*
 * 固件内部 API — 用例 / 阶段产出张量后调用本函数发布到比数缓冲。
 * 返回：0 成功；-1 缓冲已满（已调用 OnOverflow 钩子）。
 */
INT32 COMPARE_BUF_Publish(UINT16 tid, UINT16 cnt, const void *addr, UINT32 length);

/*
 * 检查桩 CPU 的清零信号。
 * 返回 true = 桩 CPU 已清零（缓冲可重用）；false = 还未消费。
 */
bool COMPARE_BUF_Consumed(void);

/*
 * 溢出告警钩子注册 — 业务初始化时调用一次。不注册时溢出静默丢弃。
 * 适配 .so 动态链接 / 跨平台，行为不依赖 weak 符号解析顺序。
 *
 *     static void OnOverflow(UINT32 alarmCode) { my_dfx_alarm(alarmCode); }
 *     COMPARE_BUF_SetOverflowHandler(OnOverflow);
 *
 * alarmCode 与 Autotest 端 errors.py::ERR_COMPARE_BUF_OVERFLOW (0x4002) 对齐。
 */
typedef void (*CompareBufOverflowHandlerFn)(UINT32 alarmCode);
void COMPARE_BUF_SetOverflowHandler(CompareBufOverflowHandlerFn handler);

/*
 * 启动期自检 — 业务初始化时调用一次。
 * 校验 g_compareBufDebugCnt / g_compareBufCompAddr 起始地址是 8B 对齐。
 * 返回 0 = OK；-1 = 起始地址未 8B 对齐（链接脚本可能放错位置）。
 */
INT32 COMPARE_BUF_SelfCheck(void);

#endif /* DUT_COMPARE_BUF_H */
