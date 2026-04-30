#ifndef DUT_DBG_CLIENT_H
#define DUT_DBG_CLIENT_H

/* 桩 CPU 调用的 API。完全靠 SUT_MemRead/Write 与被测交互。
 * 详设见 06a § 5.4。
 *
 * 使用：
 *   1. DUT_DBG_ClientInit(regionBase) —— 设定被测侧 region 起址
 *   2. 周期 DUT_DBG_RttPump 拉日志
 *   3. 周期 DUT_DBG_BeaconCheck 检测被测 crash
 *   4. 周期 DUT_DBG_CanaryCheck 扫栈金丝雀
 *   5. DUT_DBG_VarRead/Write 实现 Live Watch
 */

#include "sut_types.h"   /* 桩 CPU 侧用工程私有 ERRNO_T / UINTxx 命名 */
#include "dut_dbg.h"     /* 共享调试区布局；只引 <stdint.h> */

/* 设置被测 region 的物理基址（生产部署中由符号表查 __debug_region_base 得到）*/
ERRNO_T DUT_DBG_ClientInit(UINT32 regionBase);

/* 校验被测侧 region 已正确初始化（regionMagic + RTT magic）*/
ERRNO_T DUT_DBG_ClientHandshake(void);

/* RTT：拉一批日志，*pOutLen 返回实际取到字节数。*pOutLen=0 表示没新数据。*/
ERRNO_T DUT_DBG_RttPump(UINT8 *pOut, UINT32 cap, UINT32 *pOutLen);

/* Beacon：若被测已 crash，*pHasCrash=true 且填充 pBeacon */
ERRNO_T DUT_DBG_BeaconCheck(DutBeaconStru *pBeacon, bool *pHasCrash);

/* Canary：返回坏槽位掩码，0=全部健康 */
ERRNO_T DUT_DBG_CanaryCheck(UINT32 *pBadMask);

/* Live Watch：直接读写被测全局变量（地址由符号表预先解析得到）*/
ERRNO_T DUT_DBG_VarRead (UINT32 dutAddr, void *pOut, UINT32 size);
ERRNO_T DUT_DBG_VarWrite(UINT32 dutAddr, const void *pIn, UINT32 size);

#endif /* DUT_DBG_CLIENT_H */
