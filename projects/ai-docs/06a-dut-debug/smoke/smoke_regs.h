#ifndef SMOKE_REGS_H
#define SMOKE_REGS_H

#include "sut_types.h"

typedef enum {
    SMOKE_REG_DOORBELL = 0x0100,
    SMOKE_REG_STATUS   = 0x0104,
    SMOKE_DATA_ADDR    = 0x1000,
    SMOKE_RESULT_ADDR  = 0x2000,
} SmokeAddrEnum;

typedef enum {
    SMOKE_DOORBELL_FIRE  = 1,
    SMOKE_DOORBELL_IDLE  = 0,
    SMOKE_STATUS_DONE    = 1,
    SMOKE_STATUS_CLEAR   = 0,
    SMOKE_STATUS_DONE_MASK = 0x1,
} SmokeRegValEnum;

/* dut_dbg 在 fake mem 中的偏移（生产部署中由链接脚本固定到 RAM 某地址）*/
#define SMOKE_DUT_DBG_OFFSET    0x4000U

enum {
    SMOKE_FAKE_MEM_SIZE         = 64 * 1024,
    SMOKE_DATA_LEN              = 32,
    SMOKE_PROCESS_XOR_KEY       = 0xA5,
    SMOKE_MSG_CHAN              = 1,
    SMOKE_MSG_MAX_LEN           = 128,
    SMOKE_MSG_ECHO_LEN          = 16,
    SMOKE_FAKE_FPGA_POLL_US     = 50,
    SMOKE_MSG_POLL_US           = 100,
    SMOKE_WAIT_HAPPY_TMO_MS     = 1000,
    SMOKE_WAIT_TIMEOUT_TMO_MS   = 50,
    SMOKE_REC_SEQ_ROUNDS        = 5,
    SMOKE_LARGE_PAYLOAD_LEN     = 128,
    SMOKE_STIM_BYTE_OFFSET      = 1,
    SMOKE_MSG_REQ_STEP          = 3,
};

#endif
