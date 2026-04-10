/* PURPOSE: 从裸字节读取整数值 — 按 size 分派的 memcpy 读取
 * PATTERN: inline switch-on-size，消除 format_primitive/format_enum 的重复
 * FOR: 弱 AI 参考如何安全地从 byte buffer 读取不同宽度的整数 */

#ifndef DSC_BYTEREAD_H
#define DSC_BYTEREAD_H

#include <stdint.h>
#include <stddef.h>
#include <string.h>

/* 从 data 读取 byte_size 字节的有符号整数，符号扩展到 int64_t */
static inline int64_t dsc_read_signed(const void *data, size_t byte_size)
{
    const uint8_t *p = (const uint8_t *)data;
    switch (byte_size) {
    case 1: { int8_t  v; memcpy(&v, p, 1); return (int64_t)v; }
    case 2: { int16_t v; memcpy(&v, p, 2); return (int64_t)v; }
    case 4: { int32_t v; memcpy(&v, p, 4); return (int64_t)v; }
    case 8: { int64_t v; memcpy(&v, p, 8); return v; }
    default: return 0;
    }
}

/* 从 data 读取 byte_size 字节的无符号整数，零扩展到 uint64_t */
static inline uint64_t dsc_read_unsigned(const void *data, size_t byte_size)
{
    const uint8_t *p = (const uint8_t *)data;
    switch (byte_size) {
    case 1: { uint8_t  v; memcpy(&v, p, 1); return (uint64_t)v; }
    case 2: { uint16_t v; memcpy(&v, p, 2); return (uint64_t)v; }
    case 4: { uint32_t v; memcpy(&v, p, 4); return (uint64_t)v; }
    case 8: { uint64_t v; memcpy(&v, p, 8); return v; }
    default: return 0;
    }
}

#endif /* DSC_BYTEREAD_H */
