/*
 * compare_buf.h — 机制 B 比数协议 DUT 侧契约（详见 06b § 1.6）.
 *
 * 入口 / 全局符号：
 *   - g_debugCnt              — 当前有效比数项数（uint32_t；0 = 空）
 *   - g_compAddr[200]         — 比数描述符数组
 *
 * 协议要点：
 *   1) 生产顺序：先填 g_compAddr[g_debugCnt]，再以原子写递增 g_debugCnt
 *   2) 消费侧（桩 CPU）整体写 0 → 固件视为已消费
 *   3) 第 201 项溢出 → 触发 DFX 告警（详见 04 寄存器表），不再写
 *   4) 同 tid 多次产出用 cnt 区分；GOLDEN 按 (tid, cnt) 二维索引
 */

#ifndef DUT_COMPARE_BUF_H
#define DUT_COMPARE_BUF_H

#include <stdint.h>

#define COMPARE_BUF_CAPACITY  200u

/* 与 Python proto_test.dtypes.CompareEntry 等价；__packed 防止编译器加 padding */
typedef struct __attribute__((packed)) {
    uint16_t tid;       /* 张量 / 阶段 ID */
    uint16_t cnt;       /* 同一 tid 的第几次产出 */
    uint32_t length;    /* 数据字节数 */
    void    *addr;      /* 数据起始地址（DUT 内存空间） */
} compare_entry_t;

/* 链接脚本固定地址（详见 Q-009）；DUT 与桩 CPU 软件须一致 */
extern volatile uint32_t        g_debugCnt;
extern volatile compare_entry_t g_compAddr[COMPARE_BUF_CAPACITY];

/*
 * 固件内部 API — 用例 / 阶段产出张量后调用本函数发布到比数缓冲。
 *
 * 返回：
 *   0  成功
 *  -1  缓冲已满（应同时触发 DFX 告警）
 */
int compare_buf_publish(uint16_t tid, uint16_t cnt, const void *addr, uint32_t length);

/*
 * 检查并消费桩 CPU 的清零信号。
 * 返回 1 = 桩 CPU 已清零（缓冲可重用）；0 = 还未消费。
 */
int compare_buf_consumed(void);

#endif /* DUT_COMPARE_BUF_H */
