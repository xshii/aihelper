# 06b common/ — 工程公共头（mock）

DUT 嵌入物（`dut/`）与桩 CPU（`stub_cpu/`）共用的工程级宏 / 类型 / 工具。

| 文件 | 用途 | 真嵌入式工程对应 |
|---|---|---|
| `sut_types.h` | `UINT8/16/32/64` `INT*` `ERRNO_T` `OK/ERROR` | 工程私有 `base_types.h` / `osl_types.h` |
| `bug_check.h` | `BUG_RET / BUG_RET_VAL / BUG_CONT / BUG_BREAK` 参数校验宏 | 工程私有 `bug_check.h`（带日志路径）|
| `securec.h` | `memset_sp / memcpy_sp / strcpy_sp` + `CLEAR_STRU / CLEAR_ARRAY` | Huawei `libsecurec.a` / SafeC |
| `bitops.h` | `BIT_SET / BIT_CLR / BIT_TEST` + 掩码宏 | 工程私有 `bitops.h` |

**嵌入接入约定：**

- 头文件用 `#ifndef X` 守卫，跟工程已有定义不冲突
- mock 实现用 `static inline`，方便嵌入工程**整个目录删除**后用真版本替代
- 仅 demo 内部跑（host build / smoke 验证）保证可编译；真部署用工程私有版

**不做的事：**

- 不进 DUT 烧录镜像 — 真嵌入工程都已有自家版本
- 不替代 libc — `securec.h` mock 借标准库实现，真 securec 库自含
