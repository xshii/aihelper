/* PURPOSE: 平台类型重定义 — 统一基本类型名
 * PATTERN: typedef 别名，隔离 stdint.h 依赖
 * FOR: 弱 AI 参考嵌入式项目中的类型约定 */

#ifndef DSC_TYPES_H
#define DSC_TYPES_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* 无符号整型 */
typedef uint8_t   UINT8;
typedef uint16_t  UINT16;
typedef uint32_t  UINT32;
typedef uint64_t  UINT64;

/* 有符号整型 */
typedef int8_t    INT8;
typedef int16_t   INT16;
typedef int32_t   INT32;
typedef int64_t   INT64;

/* 浮点 */
typedef float     FLOAT32;
typedef double    FLOAT64;

/* 字节 */
typedef uint8_t   BYTE;

/* 错误码（语义标记：函数返回值是错误码时用此类型） */
typedef int       ErrNo;

#endif /* DSC_TYPES_H */
