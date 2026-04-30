#ifndef DUT_DBG_TARGET_H
#define DUT_DBG_TARGET_H

/* 被测 FPGA 内 CPU 调用的 API。生产部署中：
 *   - 由 RTOS 启动时调用 DUT_DBG_TargetInit
 *   - dbginfo 重定向到 DUT_DBG_TargetRttWrite
 *   - trap handler 调用 DUT_DBG_TargetBeaconWrite
 *   - task 创建时调用 DUT_DBG_TargetCanaryArm
 *
 * 所有函数取一个 DutDbgRegionStru* —— 地址由链接脚本固定。
 * smoke 部署中由 fake mem accessor 提供。
 *
 * 嵌入摩擦：本头只依赖 <stdint.h>（通过 dut_dbg.h），无工程私有 typedef。
 */

#include <stdint.h>
#include "dut_dbg.h"

void DUT_DBG_TargetInit(DutDbgRegionStru *pRegion);

/* RTT：写入日志环形缓冲，非阻塞，满则丢 */
void DUT_DBG_TargetRttWrite(DutDbgRegionStru *pRegion,
                            const char *pStr, uint32_t len);

/* Beacon：trap 时调用，写入完整现场后 magic 最后落，桩 CPU 据此判定 */
void DUT_DBG_TargetBeaconWrite(DutDbgRegionStru *pRegion,
                               uint32_t cause, uint32_t pc,
                               const uint32_t regs[DUT_BEACON_REGS_NUM],
                               const char *pMsg,
                               const uint8_t *pStackTop, uint32_t stackLen,
                               uint64_t timestamp);

/* Canary：task 启动时为某 slot 写入健康 pattern */
void DUT_DBG_TargetCanaryArm(DutDbgRegionStru *pRegion, uint32_t slot);

/* 仅用于演示/测试：模拟栈溢出污染某 slot */
void DUT_DBG_TargetCanaryCorrupt(DutDbgRegionStru *pRegion, uint32_t slot);

#endif /* DUT_DBG_TARGET_H */
