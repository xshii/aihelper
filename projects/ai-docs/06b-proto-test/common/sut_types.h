/*
 * sut_types.h — 工程通用类型 typedef（mock 实现）.
 *
 * 嵌入工程通常已有自己的 base_types.h / sut_types.h；本头是 demo 内部
 * 兜底，让 DUT/stub_cpu 代码无外部依赖也能编译。嵌入工程接入时若已有
 * 同名 typedef，include guard / #ifndef UINT8 守卫保证不冲突。
 */

#ifndef SUT_TYPES_H
#define SUT_TYPES_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

/* 嵌入工程已有同名 typedef 时，定义 SUT_TYPES_PROVIDED 跳过本段 */
#ifndef SUT_TYPES_PROVIDED
#define SUT_TYPES_PROVIDED
typedef uint8_t   UINT8;
typedef uint16_t  UINT16;
typedef uint32_t  UINT32;
typedef uint64_t  UINT64;
typedef int8_t    INT8;
typedef int16_t   INT16;
typedef int32_t   INT32;
typedef int64_t   INT64;
typedef float     FLOAT32;
typedef double    FLOAT64;
typedef INT32     ERRNO_T;
#endif

#ifndef OK
#  define OK     0
#  define ERROR  (-1)
#endif

#endif /* SUT_TYPES_H */
