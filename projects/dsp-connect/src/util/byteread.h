/* PURPOSE: 从裸字节读取整数值 — 按 size 分派的 memcpy 读取
 * PATTERN: inline switch-on-size，消除 format_primitive/format_enum 的重复
 * FOR: 弱 AI 参考如何安全地从 byte buffer 读取不同宽度的整数 */

#ifndef DSC_BYTEREAD_H
#define DSC_BYTEREAD_H

#include "types.h"
#include <stdint.h>
#include <stddef.h>
#include <string.h>

/* 从 data 读取 byte_size 字节的有符号整数，符号扩展到 INT64 */
static inline INT64 DscReadSigned(const void *data, UINT32 byte_size)
{
    const UINT8 *p = (const UINT8 *)data;
    switch (byte_size) {
    case 1: { INT8  v; memcpy(&v, p, 1); return (INT64)v; }
    case 2: { INT16 v; memcpy(&v, p, 2); return (INT64)v; }
    case 4: { INT32 v; memcpy(&v, p, 4); return (INT64)v; }
    case 8: { INT64 v; memcpy(&v, p, 8); return v; }
    default: return 0;
    }
}

/* 从 data 读取 byte_size 字节的无符号整数，零扩展到 UINT64 */
static inline UINT64 DscReadUnsigned(const void *data, UINT32 byte_size)
{
    const UINT8 *p = (const UINT8 *)data;
    switch (byte_size) {
    case 1: { UINT8  v; memcpy(&v, p, 1); return (UINT64)v; }
    case 2: { UINT16 v; memcpy(&v, p, 2); return (UINT64)v; }
    case 4: { UINT32 v; memcpy(&v, p, 4); return (UINT64)v; }
    case 8: { UINT64 v; memcpy(&v, p, 8); return v; }
    default: return 0;
    }
}

#endif /* DSC_BYTEREAD_H */
