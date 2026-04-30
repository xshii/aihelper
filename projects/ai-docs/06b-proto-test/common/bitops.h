/*
 * bitops.h — 位操作宏（mock 实现）.
 *
 * 嵌入工程已有同名头则替换本头。
 * 仅覆盖 codestyle § 7.2 / § 6.1 涉及的最小集；按需扩展。
 */

#ifndef BITOPS_H
#define BITOPS_H

#include <stdint.h>

/* 单字节 / 单字位操作 */
#define BIT_SET(word, bit)        ((word) |=  (1u << (bit)))
#define BIT_CLR(word, bit)        ((word) &= ~(1u << (bit)))
#define BIT_TEST(word, bit)       (((word) >> (bit)) & 1u)
#define BIT_TOGGLE(word, bit)     ((word) ^=  (1u << (bit)))

/* 位掩码 */
#define BIT_MASK(bit)             (1u << (bit))
#define BIT_RANGE_MASK(hi, lo)    ((((1u << ((hi) - (lo) + 1u)) - 1u)) << (lo))

#endif /* BITOPS_H */
