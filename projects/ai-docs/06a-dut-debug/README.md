# 06a — DUT 内存软调机制 C Demo

> 06a wiki ([../06a_子wiki_被测FPGA内存软调机制集.md](../06a_子wiki_被测FPGA内存软调机制集.md)) 的早期参考实现：在桩 CPU ↔ 被测 FPGA 只有内存读写的约束下，演示 RTT 日志 / Crash Beacon / 栈金丝雀的共享内存布局，以及 SUT 测试桩骨架。

## 目录结构

| 目录 | 角色 | 说明 |
|---|---|---|
| `common/` | 公共头 | `bug_check.h`（codestyle BUG_RET 宏）/ `sut_types.h`（UINT* 类型）|
| `dut/` | DUT 嵌入物 | 被测固件侧；最少依赖（仅 `<stdint.h>` + 公共头）|
| `stub_cpu/` | 桩 CPU 侧 | host 跑；提供 `SUT_MemRead/Write` 等访问 DUT 内存的 API |
| `smoke/` | 集成测试 | fake HAL/FPGA + 测试主入口 |

## 文件 → wiki 对照

| 路径 | 对应 wiki | 说明 |
|---|---|---|
| `dut/dut_dbg.h` | 06a § 3.2 / § 3.8 / § 3.9 | 共享调试区布局：`DutRttCbStru` + `DutBeaconStru` + `DutCanaryStru` + 顶层 `DutDbgRegionStru` |
| `dut/dut_dbg_target.{c,h}` | 被测固件侧 | 写入 RTT/Beacon/Canary，被测主循环调用 |
| `stub_cpu/dut_dbg_client.{c,h}` | 桩 CPU 侧 | 通过 `SUT_MemRead/Write` 拉取/检查同一布局 |
| `stub_cpu/sut_*.{c,h}` | 06a § 4 / § 5 | SUT 测试桩骨架（参数 / 用例 / 录像 / IO / 平台抽象） |
| `common/bug_check.h` | — | 工程级 BUG_RET / BUG_RET_VAL 宏 |
| `common/sut_types.h` | — | 大写 UINT*/INT* typedef |
| `smoke/` | — | smoke 测试入口 + fake HAL/FPGA |

## 构建

```bash
cmake -B build -S .
cmake --build build
ctest --test-dir build
```

CMake 最低 3.16（生产环境对齐）。源文件用 `file(GLOB ... CONFIGURE_DEPENDS)` 自动收集 `dut/*.c` + `stub_cpu/*.c`，新增 `.c` 文件无需修改 CMakeLists。
