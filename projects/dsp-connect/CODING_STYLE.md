# dsp-connect 编码规范

## 命名约定

| 类别 | 风格 | 例子 |
|------|------|------|
| 函数 | PascalCase | `DscReadVar()`, `DscTransportOpen()` |
| 结构体/类型 | PascalCase（无 `_t` 后缀） | `DscContext`, `DscTransport` |
| 变量 | camelCase | `elfPath`, `timeoutMs`, `byteSize` |
| 结构体字段 | camelCase | `.fieldCount`, `.byteOffset` |
| 宏/常量 | UPPER_SNAKE | `DSC_TRY`, `DSC_OK`, `DSC_ERR_NOMEM` |
| 枚举值 | UPPER_SNAKE | `DSC_TYPE_STRUCT`, `DSC_LOG_LEVEL_INFO` |
| 文件名 | snake_case | `transport_telnet.c`, `dsc_errors.h` |

## 例外：dwarf/ 目录

`src/dwarf/` 下的代码保持 **snake_case**，与 libdwarf 风格一致：
- 函数：`dsc_dwarf_open()`, `dsc_symtab_lookup()`
- 类型：`dsc_type_t`, `dsc_symbol_t`

## 类型别名

使用自定义类型名代替 stdint：

| stdint 原始类型 | 项目类型 |
|----------------|---------|
| `uint8_t` | `UINT8` |
| `uint16_t` | `UINT16` |
| `uint32_t` | `UINT32` |
| `uint64_t` | `UINT64` |
| `int8_t` | `INT8` |
| `int16_t` | `INT16` |
| `int32_t` | `INT32` |
| `int64_t` | `INT64` |
| `size_t` | `UINT32`（项目中不需要 64 位长度）|
| `bool` | **保持 `bool`** |
| `ssize_t` | `INT32` |

## 返回值类型约定

`int` 不盲目替换——按语义判断：

| 语义 | 类型 | 例子 |
|------|------|------|
| 错误码返回值 | `ErrNo`（typedef int） | `ErrNo DscReadVar(...)` |
| 布尔返回值 | `bool` | `bool DscHostIsBigEndian()` |
| 真正的整数 | `INT32` | `INT32 offset = ...` |

## 大括号风格（K&R）

所有控制流语句**必须**加大括号，即使只有一行：

```c
/* 正确 */
if (!ptr) {
    return NULL;
}

/* 错误 */
if (!ptr) return NULL;
```

## NULL 检查风格

统一使用隐式风格：
```c
if (!ptr) { ... }   /* 正确 */
if (ptr) { ... }    /* 正确 */

if (ptr == NULL) { ... }  /* 避免 */
```

## Include 顺序

```c
/* 1. 标准库 */
#include <stdint.h>
#include <stdlib.h>

/* 2. 系统/POSIX */
#include <sys/socket.h>

/* 3. 项目头文件 */
#include "dsc.h"
```
