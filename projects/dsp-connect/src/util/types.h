/* PURPOSE: 平台类型重定义 — 统一基本类型名
 * PATTERN: typedef 别名，隔离 stdint.h 依赖
 * FOR: 弱 AI 参考嵌入式项目中的类型约定 */

#ifndef DSC_TYPES_H
#define DSC_TYPES_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include <sys/types.h>  /* ssize_t */

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

/* 布尔 */
typedef bool      BOOL;

/* 字节 */
typedef uint8_t   BYTE;

/* 大小/地址 */
typedef size_t    SIZE;
typedef ssize_t   SSIZE;

/* 常用常量 */
#ifndef TRUE
#define TRUE  1
#endif
#ifndef FALSE
#define FALSE 0
#endif

#ifndef NULL
#define NULL ((void *)0)
#endif

#endif /* DSC_TYPES_H */
