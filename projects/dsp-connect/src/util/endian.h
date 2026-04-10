/* PURPOSE: 主机字节序检测 — 编译期或运行时判断
 * PATTERN: inline 函数，消除 arch_byte/arch_word 中的重复
 * FOR: 弱 AI 参考如何做可移植的字节序检测 */

#ifndef DSC_ENDIAN_H
#define DSC_ENDIAN_H

#include <stddef.h>
#include <stdint.h>

/* 检测当前主机是否为大端序（返回 1 = 大端，0 = 小端） */
static inline int dsc_host_is_big_endian(void)
{
    uint16_t val = 0x0102;
    uint8_t *bytes = (uint8_t *)&val;
    return bytes[0] == 0x01;
}

/* 就地反转 buf 的字节序 */
static inline void dsc_byte_swap(void *buf, size_t size)
{
    uint8_t *p = (uint8_t *)buf;
    for (size_t i = 0; i < size / 2; i++) {
        uint8_t tmp = p[i];
        p[i] = p[size - 1 - i];
        p[size - 1 - i] = tmp;
    }
}

#endif /* DSC_ENDIAN_H */
