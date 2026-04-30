#ifndef SUT_TYPES_H
#define SUT_TYPES_H

/* 工程若已有统一 types.h，删除本文件并改 include 该头 */

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

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

#define OK     0
#define ERROR  (-1)

#endif
