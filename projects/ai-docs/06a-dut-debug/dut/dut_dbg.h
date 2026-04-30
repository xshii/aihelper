#ifndef DUT_DBG_H
#define DUT_DBG_H

/* ============================================================
 *  共享内存调试区 — 被测 FPGA 与桩 CPU 共看同一份布局
 *
 *  机制：RTT 日志 / Crash Beacon / 栈金丝雀 / 变量读写
 *  详设：见 06a § 3.2 / § 3.8 / § 3.9
 *
 *  生产部署：被测固件链接脚本将本结构固定在 RAM 某地址。
 *  smoke 部署：放在 fake mem 偏移 DUT_DBG_REGION_OFFSET 处。
 *
 *  嵌入选项（编译时 -D 覆盖）：
 *    DUT_RTT_BUF_SIZE     RTT 环形缓冲字节数（默认 1024）
 *    DUT_BEACON_REGS_NUM  寄存器现场数量    （默认 32）
 *    DUT_BEACON_MSG_LEN   panic 消息长度    （默认 64）
 *    DUT_BEACON_STACK_LEN 栈 dump 长度      （默认 256）
 *    DUT_CANARY_SLOTS     金丝雀槽数        （默认 8）
 *
 *  本头只引 <stdint.h> / <stddef.h>，不依赖任何工程私有 typedef。
 * ============================================================ */

#include <stdint.h>
#include <stddef.h>

/* --- 区头 --- */
#define DUT_DBG_REGION_MAGIC    0xD06DBE60U   /* "dog-debug" */

/* --- RTT 日志通道（被测→桩 CPU）--- */
#define DUT_RTT_MAGIC_STR       "RTT-CB\0"    /* 7 字节 + null */

#ifndef DUT_RTT_BUF_SIZE
#  define DUT_RTT_BUF_SIZE      1024U
#endif

typedef struct {
    char     magic[8];                /* "RTT-CB\0" */
    uint32_t bufSize;
    uint32_t wrOff;                   /* 被测写指针（volatile）*/
    uint32_t rdOff;                   /* 桩 CPU 读指针（volatile）*/
    uint8_t  buffer[DUT_RTT_BUF_SIZE];
} DutRttCbStru;

/* --- Crash Beacon（被测 trap 时写）--- */
#define DUT_BEACON_MAGIC_STR    "CRASH!!"     /* 7 字节 + null */

#ifndef DUT_BEACON_REGS_NUM
#  define DUT_BEACON_REGS_NUM   32U
#endif
#ifndef DUT_BEACON_MSG_LEN
#  define DUT_BEACON_MSG_LEN    64U
#endif
#ifndef DUT_BEACON_STACK_LEN
#  define DUT_BEACON_STACK_LEN  256U
#endif

typedef struct {
    char     magic[8];                /* "CRASH!!\0"，最后写入；桩 CPU 据此判定 */
    uint64_t timestamp;
    uint32_t cause;                   /* RISC-V mcause 或自定义 */
    uint32_t pc;                      /* 出错 PC */
    uint32_t sp;
    uint32_t ra;
    uint32_t regs[DUT_BEACON_REGS_NUM];
    uint8_t  msg[DUT_BEACON_MSG_LEN]; /* 可选 panic 消息 */
    uint8_t  stackDump[DUT_BEACON_STACK_LEN];
} DutBeaconStru;

/* --- 栈金丝雀（每 task 一个槽）--- */
#define DUT_CANARY_PATTERN      0xDEADBEEFU

#ifndef DUT_CANARY_SLOTS
#  define DUT_CANARY_SLOTS      8U
#endif

typedef struct {
    uint32_t slot[DUT_CANARY_SLOTS];  /* 健康时全等于 DUT_CANARY_PATTERN */
} DutCanaryStru;

/* --- 顶层区结构 --- */
typedef struct {
    uint32_t        regionMagic;      /* DUT_DBG_REGION_MAGIC */
    uint32_t        regionSize;
    DutRttCbStru    rtt;
    DutBeaconStru   beacon;
    DutCanaryStru   canary;
} DutDbgRegionStru;

/* 桩 CPU 通过 SUT_MemRead/Write + 这些偏移访问，与目标侧布局一致 */
#define DUT_DBG_OFF_REGION_MAGIC   0U
#define DUT_DBG_OFF_RTT            ((uint32_t)offsetof(DutDbgRegionStru, rtt))
#define DUT_DBG_OFF_BEACON         ((uint32_t)offsetof(DutDbgRegionStru, beacon))
#define DUT_DBG_OFF_CANARY         ((uint32_t)offsetof(DutDbgRegionStru, canary))

/* 编译期防御：嵌入工程改 -D 覆盖默认值时挡住越界 */
_Static_assert(DUT_BEACON_REGS_NUM >= 3,
               "BeaconWrite uses regs[1]=ra, regs[2]=sp");
_Static_assert(DUT_CANARY_SLOTS <= 32,
               "CanaryCheck builds bad-mask via (1U << i); slots > 32 would overflow");

#endif /* DUT_DBG_H */
