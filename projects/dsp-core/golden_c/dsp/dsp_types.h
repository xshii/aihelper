#pragma once

// Block size 常量
#define DSP_BLOCK_BITS 128
#define DSP_BLOCK_BYTES (DSP_BLOCK_BITS / 8)

// QFormat, q12_22_t, q24_40_t, BINT8/16/32 定义在 current/include/ 下
// dsp_convert.h 加 using bint8 = BINT8 等别名
