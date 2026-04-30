# 子 Wiki 6A：被测 FPGA 内存软调机制集

> **文档定位**：在"桩 CPU 与被测 FPGA 之间**只有内存读写**"这个强约束下，能做到什么调试能力。本文档系统梳理业界相关方法（SEGGER RTT、GDB stub、kprobes/ftrace、eBPF、coredump 等），并给出在本项目落地的方案集。
>
> **与上游 wiki 的分工**：
> - [子 wiki 6](./06_子wiki_Autotest软件架构.md)：跨平台架构、PlatformAdapter
> - [子 wiki 6B](./06b_子wiki_原型测试环境详设.md)：FPGA 平台落地详设、A/B 双交互机制、桩 CPU C 代码
> - **本文档（6C）**：机制 B（SoftDebug 内存读写）能力延伸——把"只能读写内存"用到极致
>
> **抽象层次**：6C 描述的所有机制都是**机制 B 的能力扩展**，对上游能力服务层不可见。共用同一套 SoftDebug 基础设施（`SUT_MemRead/Write/Wait`）和符号表（`g_dut_symtab[]`）。
>
> **核心论点**：内存读写 + 符号表 + 被测固件少量配合，足以模拟 95% 的传统 JTAG debug 能力。

---

## 目录

0. [背景：内存读写的能力边界](#0-背景内存读写的能力边界)
1. [业界对照](#1-业界对照)
2. [设计原则](#2-设计原则)
3. [机制集](#3-机制集)
   - 3.0 全局变量地址解析机制
   - 3.1 命令通道与函数调用门（引用 6B）
   - 3.2 [高速日志通道（RTT 风格）](#32-高速日志通道rtt-风格)
   - 3.3 [环形事件追踪（ftrace 风格）](#33-环形事件追踪ftrace-风格)
   - 3.4 [软件断点（kprobe 风格）](#34-软件断点kprobe-风格)
   - 3.5 [函数入口 Hook（编译期 NOP padding）](#35-函数入口-hook编译期-nop-padding)
   - 3.6 [PC 采样性能分析](#36-pc-采样性能分析)
   - 3.7 [代码覆盖率收集](#37-代码覆盖率收集)
   - 3.8 [栈金丝雀](#38-栈金丝雀)
   - 3.9 [黑匣子 Crash Beacon](#39-黑匣子-crash-beacon)
   - 3.10 [按需 Coredump](#310-按需-coredump)
   - 3.11 [实时变量监视（Live Watch）](#311-实时变量监视live-watch)
   - 3.12 [热补丁与配置热更新](#312-热补丁与配置热更新)
4. [共用基础设施 — RTOS 最小契约](#4-共用基础设施)
5. [模块详细设计 — 被测/桩 CPU 职责分割](#5-模块详细设计--被测--桩-cpu-职责分割)
6. [实施优先级与路线图](#6-实施优先级与路线图)
7. [待澄清清单](#7-待澄清清单)
8. [附录：参考资料](#附录参考资料)

---

## 0. 背景：内存读写的能力边界

### 0.1 约束

桩 CPU ↔ 被测 FPGA 之间，物理通道只剩 **SoftDebug 内存读写**：

- ✅ 任意地址读
- ✅ 任意地址写（含代码段——如果被测固件没开 MPU 写保护）
- ✅ 桩 CPU 持有被测 ELF 符号表（function、global、struct layout、line info）
- ❌ 没有 IPI / Doorbell / 中断注入
- ❌ 没有 JTAG halt / step
- ❌ 没有 ETM / ETB 硬件 trace
- ❌ 没有 PMU 性能计数器直读

### 0.2 关键洞察

只要被测固件**愿意配合**（在主循环里挂一个 dispatcher），桩 CPU 就能用"轮询应答"模拟出几乎所有传统调试能力。具体能力清单见 § 3 各机制。

业界判例：SEGGER J-Link 的 RTT 就是纯内存访问实现，~500B ROM 即可达成对运行中应用完全透明的高速 I/O——SoftDebug 软调与 J-Link 的"background memory access"性质相同，RTT 能做的事我们都能做。

---

## 1. 业界对照

| 工具 | 核心机制 | 借鉴 |
|---|---|---|
| **SEGGER RTT** | 共享内存 control block + 多通道环形缓冲 | § 3.2 |
| **Linux kprobes** | 替换指令首字节为 trap，trap handler 中处理 | § 3.4 |
| **ftrace** | 编译期插桩 + per-CPU 环形缓冲 | § 3.3 / § 3.5 |
| **gcov** | 编译期注入 edge counter | § 3.7 |
| **minicoredumper** | 选择性 coredump，4KB 级精简 | § 3.10 |
| **kpatch / kGraft** | 函数级热补丁，prologue 跳板 | § 3.12 |

> 其他参考（GDB RSP / eBPF / DTrace / SystemView 等）见附录。

---

## 2. 设计原则

1. **被测侧零代价或最小代价**：每个机制对被测固件的侵入要可量化（ROM/RAM/CPU%）。能编译期开关的优先。
2. **共用一套基础设施**：所有机制共享同一块 `dut_debug_region`（symbol-table-driven），不要每个机制各占一段地址。
3. **单向 vs 双向区分**：纯观察类（日志、trace、PC 采样、coverage）只需被测侧"写"、桩 CPU "读"——**不需要 dispatcher**，最便宜。需要被测侧响应的（函数调用、断点、coredump）才走 dispatcher。
4. **优雅降级**：被测固件未集成某机制时，桩 CPU 侧 API 报 `ERR_FEATURE_NOT_PROBED`，不挂死。
5. **生产可留**：`SUT_RECORD=0/1` 类似的编译开关——release 版本可以保留 0% 开销的 hook 点（"trampoline NOP"），dev 版本启用。

---

## 3. 机制集

### 3.0 全局变量地址解析机制

后续 3.x 机制（RTT / ftrace / coredump / live watch / 比数契约 …）都依赖"主机侧拿到被测固件全局变量的地址"。这层能力**先于所有机制存在**，单独设计。

#### 候选方案

| # | 方案 | 输入 | 何时选 |
|---|---|---|---|
| 1 | **ELF 符号表解析（首选）** | 编译产物 `.elf`，未 strip | 默认方案。`pyelftools` / `nm` / `objdump` 直接读符号表；DWARF 还能给类型信息。能用就优先用 |
| 2 | **MAP 文件解析** | 链接器输出 `.map` | CI 环境不带 pyelftools / 想避免 ELF 库依赖时用。文本格式 `符号 地址 大小`，grep 即可 |
| 3 | **链接脚本 / scatter file 钉死地址** | `__attribute__((section(".fixed_dbg")))` + ld script `.fixed_dbg : { . = 0xXXXX; ... }` | 用于"地址必须固定"的 magic 区（RTT 控制块、bug check buffer），方法 1/2 可能产生不同 build 不同地址 |
| 4 | **锚点表（anchor table）** | 固定地址放一个 `{magic, name, addr, size}[]` 目录 | 符号特别多 / 想避免 N 个 section 时用。RTT 控制块本质就是这套（`DUT_RTT_MAGIC` + `RTT_CB`）。host 先读目录再跳转 |
| 5 | **Section 边界符号** | `__attribute__((section("xxx")))` + `__start_xxx` / `__stop_xxx` | 适合"一类注册项"（事件 ID 表、探针表、测试 case 表），让链接器自动给边界。本文档 § 3.3 ftrace 静态事件登记走这个 |
| 6 | **Boot 日志 emit + 主机解析** | 启动时 `printf("&g_xxx=0x%p", &g_xxx)` | 兜底。前面方案都不可用 / debug 期临时插入时 |

#### 选型矩阵

| 场景 | 推荐方案 | 理由 |
|---|---|---|
| 普通业务全局变量（`g_compareBuf*` / 普通状态字 / `g_bug_check_buf`）| **方案 1** | 编译产物自带，无需固件配合 |
| Magic 控制块（RTT_CB / DBG_REGION_HEADER / Crash Beacon）| **方案 3** | 固定地址 = 跨 build 稳定 = host 可硬编码 |
| 同类批量项（事件 ID / 探针 / 软断点表）| **方案 5** | 链接器自动给边界，新增项不动 host 代码 |
| 大量符号 + 不想多个 section | **方案 4** | 一处目录、host 一次读取 |
| 符号被 strip / 没有 ELF | **方案 2** | MAP 通常仍保留；再不济 6 |
| 调试期临时验证 | **方案 6** | 改个 printf 即可，不重新出包 |

#### 不推荐 / 仅兜底

- **Magic 扫内存**：没符号没 boot 日志才用，慢且脆。
- **GDB/JTAG MI 查符号**：需要 debugger 始终在线，不适合自动化。

后续 3.x 机制描述里出现的"主机侧已知 `g_xxx` 地址"全部依赖本节，**不再重复说明地址来源**。

### 3.1 命令通道与函数调用门（引用 6B）

详见 [子 wiki 6B § 3.11 Memory Invocation Gate](./06b_子wiki_原型测试环境详设.md)。本文档其他机制复用同一块 `call_gate_t` 数据结构和 `dispatcher_poll` 入口。

复用规则：
- `call_gate_t.magic` 高 16 位是 **机制类型**，低 16 位是 **状态**
- `0xCA110000`（call request） / `0xD0E00000`（call done）已用
- 后续机制按下表分配：

| 机制类型 (高 16 位) | 用途 | 节 |
|---|---|---|
| `0xCA11` | 函数调用请求 | 6B § 3.11 |
| `0xB901` | 软断点 hit 通告 | § 3.4 |
| `0xC0DE` | coredump 请求 | § 3.10 |
| `0xFA7C` | 热补丁应用 | § 3.12 |
| 其他 | 单向通道（日志/trace/PC 采样）不占 magic | — |

### 3.2 高速日志通道（RTT 风格）

#### 设计

被测固件的 `dbginfo()` 不再写 UART，而是写到 **共享内存环形缓冲**。桩 CPU 后台轮询该 buffer，导出到工程目录。

```c
/* 被测 FPGA 侧 —— 固定地址 */
#define DUT_RTT_MAGIC   "RTT-CB\0\0"
#define DUT_RTT_UP_BUF_SIZE   4096
#define DUT_RTT_DOWN_BUF_SIZE 64

typedef struct {
    char     name[16];
    uint8_t *pBuffer;          /* 缓冲区基址 */
    uint32_t size;
    volatile uint32_t wrOff;   /* 被测侧写指针 */
    volatile uint32_t rdOff;   /* 桩 CPU 读指针 */
    uint32_t flags;            /* 0=非阻塞丢弃，1=阻塞 */
} rtt_channel_t;

typedef struct {
    char            magic[16];     /* "RTT-CB" + version */
    uint32_t        up_count;       /* DUT → 桩 CPU 通道数 */
    uint32_t        down_count;     /* 桩 CPU → DUT 通道数 */
    rtt_channel_t   up[3];          /* 0=日志, 1=trace, 2=binary dump */
    rtt_channel_t   down[1];        /* 0=控制命令 */
} rtt_control_block_t;

extern rtt_control_block_t g_rtt_cb __attribute__((section(".rtt")));
```

#### 被测固件侧 `dbginfo` 实现

```c
void dbginfo(const char *fmt, ...)
{
    char buf[128];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);

    rtt_channel_t *ch = &g_rtt_cb.up[0];
    uint32_t wr = ch->wrOff;
    uint32_t rd = ch->rdOff;        /* 桩 CPU 在改这个，volatile 读 */
    uint32_t free = (rd > wr) ? (rd - wr - 1) : (ch->size - wr + rd - 1);
    if ((uint32_t)n > free) {
        if (ch->flags == 0) return;  /* 非阻塞，丢弃 */
        while ((uint32_t)n > free) { /* 阻塞等桩 CPU 消费 */ }
    }
    /* 写入环形缓冲（处理回绕）*/
    for (int i = 0; i < n; i++) {
        ch->pBuffer[(wr + i) % ch->size] = buf[i];
    }
    __sync_synchronize();
    ch->wrOff = (wr + n) % ch->size;
}
```

#### 桩 CPU 侧拉取

```c
ERRNO_T DUT_RttPoll(uint32_t channel, uint8_t *out, uint32_t cap, uint32_t *outLen)
{
    uint32_t wr, rd, size;
    uint32_t base = DUT_RTT_CB_ADDR + offsetof(rtt_control_block_t, up[channel]);
    SUT_MemRead(base + offsetof(rtt_channel_t, wrOff), &wr, 4);
    SUT_MemRead(base + offsetof(rtt_channel_t, rdOff), &rd, 4);
    SUT_MemRead(base + offsetof(rtt_channel_t, size),  &size, 4);
    if (wr == rd) { *outLen = 0; return OK; }

    uint32_t avail = (wr >= rd) ? (wr - rd) : (size - rd + wr);
    uint32_t take  = (avail < cap) ? avail : cap;
    /* 处理回绕，分两次读 */
    if (rd + take <= size) {
        SUT_MemRead(DUT_RTT_BUF_ADDR(channel) + rd, out, take);
    } else {
        uint32_t first = size - rd;
        SUT_MemRead(DUT_RTT_BUF_ADDR(channel) + rd, out, first);
        SUT_MemRead(DUT_RTT_BUF_ADDR(channel),      out + first, take - first);
    }
    /* 推进 rdOff */
    uint32_t newRd = (rd + take) % size;
    SUT_MemWrite(base + offsetof(rtt_channel_t, rdOff), &newRd, 4);
    *outLen = take;
    return OK;
}
```

#### 关键收益

- 被测侧写日志接近内存速度（不卡 UART）
- 桩 CPU 侧后台拉取，对被测**完全透明**
- 多通道：日志 / trace / 二进制 dump 各走各的
- ROM ~500B（与 SEGGER RTT 一致）

### 3.3 环形事件追踪（ftrace 风格）

#### 设计

类似 ftrace 的 per-CPU ring buffer，但只需要一个 buffer（被测 FPGA 单核场景）。每条事件定长 32 字节：

```c
typedef struct {
    uint64_t timestamp;     /* 时间戳（cycle 计数）*/
    uint16_t event_id;      /* 事件类型（编译期分配）*/
    uint16_t cpu_id;        /* 单核固定为 0 */
    uint32_t arg0;
    uint32_t arg1;
    uint32_t arg2;
    uint32_t arg3;
    uint32_t reserved;
} trace_event_t;

/* 被测固件中的 trace 入口 —— inline 极致快 */
static inline void TRACE(uint16_t id, uint32_t a, uint32_t b, uint32_t c, uint32_t d)
{
    if (!g_trace_enabled) return;       /* 一次比较，可被分支预测吃掉 */
    uint32_t idx = __sync_fetch_and_add(&g_trace_wr, 1) & TRACE_MASK;
    trace_event_t *e = &g_trace_buf[idx];
    e->timestamp = read_cycle_counter();
    e->event_id  = id;
    e->arg0 = a; e->arg1 = b; e->arg2 = c; e->arg3 = d;
}
```

#### 静态事件 ID 自动登记（编译期）

```c
/* 被测代码里这样写 */
TRACE_EVENT_DEFINE(EV_MODEL_START,  "model_start",  "model_id=%u, mode=%u");
TRACE_EVENT_DEFINE(EV_TENSOR_DONE,  "tensor_done",  "stage=%u, addr=0x%x");

void on_model_start(uint32_t model_id, uint32_t mode) {
    TRACE(EV_MODEL_START, model_id, mode, 0, 0);
    /* ... */
}

/* 编译期收集所有 TRACE_EVENT_DEFINE 进 .trace_meta section
 * 桩 CPU 启动时读这个 section，知道每个 event_id 的名字和 fmt */
```

#### 桩 CPU 侧消费

```c
ERRNO_T DUT_TracePoll(trace_event_t *out, uint32_t cap, uint32_t *outCount)
{
    /* 同 RTT，读 wr/rd 指针 + 拉数据 */
}

void DUT_TraceFormatLine(const trace_event_t *e, char *out, uint32_t cap)
{
    const trace_event_meta_t *meta = trace_meta_lookup(e->event_id);
    snprintf(out, cap, "[%llu] %s: ", e->timestamp, meta->name);
    snprintf(out, cap, meta->fmt, e->arg0, e->arg1, e->arg2, e->arg3);
}
```

#### 收益

- 单事件 < 50 cycle，可在中断里 trace
- 主机侧能重建完整时间线（类似 SystemView / Tracealyzer）
- 被测侧 `g_trace_enabled` 开关控制，release 版本设 0 编译器全部优化掉

### 3.4 软件断点（kprobe 风格）

#### 原理

kprobes 的核心：**把目标指令的首字节改成 trap 指令，trap handler 里通知调试器，并在恢复后单步执行原指令**。

我们能不能做？看条件：
- ✅ 内存能写代码段（前提：被测固件没开 MPU 代码只读）
- ✅ 被测有 trap handler
- ⚠️ 没有"单步执行"硬件——需要技巧

#### 简化版：一次性断点

实现思路：桩 CPU 备份目标地址原指令 → 写 trap 指令（RISC-V `ebreak` / ARM `BKPT`）→ 刷 I-cache → 被测 trap handler 通过 call_gate 上报现场（PC + 通用寄存器）→ 桩 CPU 调 callback → 恢复原指令并 ack。

**局限明显**：一次性（恢复后失效；永久断点需单步硬件或指令模拟器，复杂度陡升）；代码段必须可写；I-cache 一致性必须处理；多断点 thread-safe。**不做交互式断点**（那是 GDB 的工作）。多数场景**优先考虑 § 3.5 编译期 NOP padding 方案**——零运行期成本、永久 hook、不碰指令 cache。

### 3.5 函数入口 Hook（编译期 NOP padding）

比软断点温和、永久有效、零中断开销，适合 trace / 参数 dump / 错误注入 / 性能测量。

**实现方案**：编译期给可 hook 的函数入口预留 NOP padding，运行期由桩 CPU 改写为跳转。GCC `patchable_function_entry` 直接产出（**Linux ftrace 就是这么做的**）：

```c
#define HOOKABLE __attribute__((patchable_function_entry(8, 0)))

HOOKABLE int dut_run_model(int id) { ... }
```

未启用时零开销；启用时桩 CPU 改写 NOP 为跳转到 hook trampoline，trampoline 完成桩工作后跳回 `target+N`。

> 运行期反汇编原 prologue 拷贝到 trampoline 末尾的方案（Capstone / LLVM disassembler 集成）需要被测构建配合较少但桩 CPU 复杂度高，本工程**不采用**——优先编译期方案。

### 3.6 PC 采样性能分析

桩 CPU 没有"直接读 PC"的通道，方案是 **被测侧 timer ISR 周期写 PC 到共享 buffer**：

```c
/* RISC-V timer ISR：从 mepc CSR 读出被打断时的 PC */
void timer_isr(void)
{
    uint32_t pc;
    asm volatile ("csrr %0, mepc" : "=r"(pc));
    g_pc_sample_buf[g_pc_sample_idx++ & MASK] = pc;
}
```

桩 CPU 后台拉 `g_pc_sample_buf`，按符号表归类后喂 `flamegraph.pl`，得到统计意义的性能 profile。**有 ISR 侵入成本**（每次中断 ~10 cycle），ISR 频率与采样精度权衡按用例需要决定。

### 3.7 代码覆盖率收集

被测编译时加 `-fprofile-arcs -ftest-coverage`，每条 edge 一个 counter。把 counter 区放进一个固定 section（`.cov_counters`），用 § 3.0 方案 5（section 边界符号）让链接器给出 start/end，桩 CPU teardown 时整段读出，结合 ELF line info 走标准 lcov 工具链生成报告。

**收益**：用例集覆盖率报告（首用例验收阈值），几乎零运行时开销（只是 counter 自增）。

### 3.8 栈金丝雀

被测固件每个 task 的栈底预留 32 字节固定 pattern，桩 CPU 周期性读栈底，pattern 不一致 → 栈溢出告警：

```c
__attribute__((section(".canary"))) uint8_t g_canary_pattern[] = {
    0xDE, 0xAD, 0xBE, 0xEF, /* ... */
};

void task_init(void) {
    memcpy(stack_bottom, g_canary_pattern, 32);
}
```

> 堆红区（穷人 ASAN）需要包装 malloc / free，侵入面较大，本工程**不实现**——堆问题用厂商 RTOS 自带 heap-check 或 valgrind 风格离线工具兜底。

### 3.9 黑匣子 Crash Beacon

#### 原理

被测 trap / panic / assert 失败时，**第一时间把现场写到固定地址**，然后才尝试 reset / hang / 上报。桩 CPU 即便看到"被测死了"，也能从 beacon 区拿到事故现场。

```c
typedef struct {
    char     magic[8];           /* "CRASH!!\0" */
    uint64_t timestamp;
    uint32_t cause;              /* trap cause / assert id */
    char     msg[64];
    uint32_t pc, sp, ra;
    uint32_t regs[32];
    uint8_t  stack_dump[256];    /* 栈顶 256 字节 */
    uint32_t last_traces[16];    /* 最近 16 条 trace event */
} crash_beacon_t;

extern crash_beacon_t g_crash_beacon __attribute__((section(".beacon")));

/* 被测侧 panic 路径 */
void __noreturn dut_panic(const char *msg)
{
    memcpy(g_crash_beacon.magic, "CRASH!!\0", 8);
    g_crash_beacon.timestamp = read_cycle_counter();
    strncpy(g_crash_beacon.msg, msg, 64);
    snapshot_registers(&g_crash_beacon);
    snapshot_stack_top(&g_crash_beacon);
    snapshot_last_traces(&g_crash_beacon);
    __sync_synchronize();        /* 屏障：先写完才能挂 */

    while (1) { __wfi(); }       /* 死循环等桩 CPU 救援 */
}
```

#### 桩 CPU 救援动作

```c
ERRNO_T DUT_RescueOnDeath(void)
{
    char magic[8];
    SUT_MemRead(DUT_BEACON_ADDR, magic, 8);
    if (memcmp(magic, "CRASH!!\0", 8) != 0) return ERR_NO_BEACON;

    crash_beacon_t beacon;
    SUT_MemRead(DUT_BEACON_ADDR, &beacon, sizeof(beacon));

    /* 翻译 PC → 函数名 + 行号（用符号表 + DWARF）*/
    const char *fn = symtab_addr_to_func(beacon.pc);
    uint32_t line = dwarf_addr_to_line(beacon.pc);

    /* 整套现场归档进用例 artifact */
    archive_crash_report(&beacon, fn, line);
    return OK;
}
```

类似 Linux 内核的 panic notifier、Tracealyzer 的 hardfault hook。**FAIL 现场 100% 可追溯**——这是 NFR-04 的关键支撑。

### 3.10 按需 Coredump

#### 原理

被测正常运行中，桩 CPU 想"偷一份完整内存快照"用于离线分析（GDB 加载 ELF + core 文件，可以做事后调试）。

#### 协作模式

桩 CPU 写 magic `0xC0DE0000` → 被测 dispatcher 关中断、写 task list 与寄存器组到 scratch、置 magic `0xC0DE_READY` → 桩 CPU 按段读 `.data` / `.bss` / 各 task stack → 写 magic `0xC0DE_DONE` → 被测恢复中断继续。桩 CPU 输出标准 ELF core 格式，配合 DUT.elf 直接 `riscv-gdb DUT.elf core` 启动**事后调试**。

#### 借鉴：minicoredumper

只 dump 关心的段（不 dump 全 RAM 节省 4 个量级空间）：
- 所有 task TCB + stack
- 所有 `.data` / `.bss`（编译期标记的）
- 最近 N 条 trace event
- 当前 PC + 寄存器组

典型场景下 4~64 KB 即可保留完整事后定位能力。

### 3.11 实时变量监视（Live Watch）

#### 原理

桩 CPU 周期性读一组关心的全局变量，主机侧实时画图——类似 IDE 的 Watch 窗口，但完全靠内存读做。**无需被测侧任何改动**。

#### 实现

```c
typedef struct {
    const char *name;
    uint32_t    addr;       /* 从符号表查 */
    uint32_t    size;
    uint32_t    period_ms;  /* 桩 CPU 拉取周期 */
} watch_entry_t;

static watch_entry_t g_watches[] = {
    { "g_dut_state",    0, sizeof(state_t),  100 },
    { "g_model_progress", 0, 4,              50  },
};

void DUT_WatchInit(void) {
    for (int i = 0; i < N; i++) {
        g_watches[i].addr = symtab_lookup(g_watches[i].name)->addr;
    }
}

/* 主循环 */
void DUT_WatchTick(void) {
    for (int i = 0; i < N; i++) {
        if (now() - last_read[i] >= g_watches[i].period_ms) {
            uint8_t buf[64];
            SUT_MemRead(g_watches[i].addr, buf, g_watches[i].size);
            archive_watch_sample(g_watches[i].name, buf);
        }
    }
}
```

#### 收益

- 实时仪表盘（用例运行中能看到关键变量轨迹）
- 配合时间线，做"为什么 g_state 在第 30s 变 ERROR"的回放分析
- 零侵入

### 3.12 热补丁与配置热更新

#### 配置热更新（无需重启）

把所有可调参数集中到 **config struct**，被测主循环每 N ms 检查 config 版本号：

```c
typedef struct {
    uint32_t version;      /* 桩 CPU 改这个，被测看到 version 变就 reload */
    uint32_t timeout_ms;
    uint32_t batch_size;
    /* ... */
} dut_config_t;

extern dut_config_t g_dut_config __attribute__((section(".config")));

/* 被测主循环 */
void main_loop(void) {
    static uint32_t last_ver = 0;
    if (g_dut_config.version != last_ver) {
        apply_config(&g_dut_config);
        last_ver = g_dut_config.version;
    }
}
```

桩 CPU 写新值 → 写新 version → 被测下次 tick 自动应用。

#### 函数级热补丁

思路类似 Linux kpatch / livepatch：单独编译 patch.elf → 写入 `.text_patch` 预留区 → 用 § 3.5 的 hook 改写原函数入口跳到 patch → flush I-cache。**仅用于故障注入场景**（"让 alloc 失败 50% 概率"），实施前需 ISP 团队评估 ABI / 链接段 / cache 一致性细节，本文档不展开。

---

## 4. 共用基础设施

> 共享内存布局、API 命名、编译开关详见 § 5.2 / § 5.3 / § 5.4。本节只讲 RTOS 契约。

### 4.1 RTOS 最小契约（自研 RTOS 适配）

自研 RTOS 不一定有标准 hook（idle hook、trace 钩子、TCB 标准布局）。本节定义 debug 库对 RTOS 的**最小依赖契约**，只要满足这一份头文件，所有机制都能跑。

#### 必选契约（5 项）

```c
/* dut_debug_contract.h —— 自研 RTOS 必须提供 */

/* 1. 调试任务入口：RTOS 在低优 task 或 idle 循环里调用此函数。
 *    debug 库提供，RTOS 只负责"找个地方调它"。*/
void dut_debug_dispatcher_poll(void);

/* 2. trap 钩子：trap handler 第一行调用此函数（弱符号默认空实现）。
 *    传入 cause、pc 和完整 32 寄存器组（RV32 / RV64 自适应）。*/
void dut_debug_trap_hook(uint32_t cause, uint32_t pc, uint32_t *regs);

/* 3. ISR 上下文标志：让 debug 库知道当前是否在中断中（决定能否阻塞）。*/
extern volatile uint32_t g_dut_in_isr_count;

/* 4. cycle 计数器读取（mcycle CSR 在 U-mode 不一定可读，RTOS 包装）。*/
uint64_t rtos_get_cycle(void);

/* 5. 临界区（写共享内存时关中断保护）。*/
uint32_t rtos_disable_irq(void);
void     rtos_restore_irq(uint32_t saved);
```

#### 可选契约（解锁高级机制）

```c
/* 满足这一项才能解锁完整 Coredump（§ 3.10），否则只能 dump 当前 task。*/
typedef struct {
    void    *task_list_head;        /* 任务链表头指针 */
    uint32_t tcb_size;
    uint32_t tcb_next_offset;       /* TCB 中"下一个 TCB 指针"的偏移 */
    uint32_t tcb_stack_offset;      /* TCB 中"栈顶指针"的偏移 */
    uint32_t tcb_name_offset;       /* TCB 中"任务名"的偏移 */
    uint32_t tcb_state_offset;
} rtos_tcb_layout_t;

extern const rtos_tcb_layout_t g_rtos_tcb_layout;
```

#### 集成成本估算

| 项 | 自研 RTOS 改动 |
|---|---|
| dispatcher 接入 | 创建一个低优 task 调 `dut_debug_dispatcher_poll`，~5 行 |
| trap hook 接入 | trap entry 第一句加 `dut_debug_trap_hook(...)`，~3 行 |
| ISR 计数 | enter/exit ISR 时 `g_dut_in_isr_count++/--`，~2 行 |
| cycle / irq 包装 | 4 个简单包装函数，~30 行 |
| TCB layout 描述符 | 1 个常量结构体，~10 行 |
| **合计** | **~50 行胶水**，**零架构改动** |

#### 退化方案（契约不满足时）

| 契约项缺失 | 影响范围 | 替代方案 |
|---|---|---|
| dispatcher 入口 | 函数调用门 / 软断点 / coredump / 热补丁 全部下线 | 改在 trap_hook 里被动响应（性能差但能跑）|
| trap_hook | Crash Beacon 下线，软断点下线 | 仅靠桩 CPU 侧"看到死了就硬复位 + 收尸" |
| g_in_isr_count | RTT 多任务/ISR 共写时可能撕裂 | 限制 dbginfo 不在 ISR 里调 |
| cycle 计数器 | trace 时间戳精度降级 | 用桩 CPU 侧时间戳近似（精度 ms 级）|
| irq 关中断 | 共享内存写有竞态 | 全部用 `amoadd.w` 原子访问绕过 |
| TCB layout | Coredump 退化为单 task + 全局段 | 大多数定位场景仍够用 |

**结论**：5 必选契约只要 ~50 行胶水；即使一项都不满足，仍有 3 个机制完全可工作（Live Watch / Coverage / Canary）。

---

## 5. 模块详细设计 — 被测 / 桩 CPU 职责分割

### 5.1 职责总览矩阵

| 模块 | 共享数据结构 | **被测 FPGA 内 CPU 做** | **桩 CPU 做** | 单向/双向 | 需 dispatcher | 需 trap_hook |
|---|---|---|---|---|---|---|
| M-CALL 函数调用门 | `call_gate_t` | 轮询 magic + 调目标函数 + 写 result | 写参数 → 触发 → 读 result | 双向 | ✓ | — |
| M-RTT 高速日志 | `rtt_control_block_t` | 写环形 buffer | 后台拉取 + 落盘 | 单向↑ | — | — |
| M-TRACE 事件追踪 | `trace_buf_t[N]` + `trace_meta` | inline TRACE 写事件 | 拉取 + 时间线归档 | 单向↑ | — | — |
| M-COV 覆盖率 | `.cov_counters` 段 | 编译期注入 counter 自增 | teardown 整段读 + 生成 lcov | 单向↑ | — | — |
| M-CANARY 金丝雀 | `.canary` 段 | 启动写 pattern | 周期 scan，pattern 变即告警 | 单向↑ | — | — |
| M-BEACON Crash | `crash_beacon_t` | trap 时写现场 | 检测 magic → 收尸归档 | 单向↑ | — | ✓ |
| M-WATCH Live Watch | 全局变量本身 | **零参与** | 周期读符号表中变量 | 单向↑ | — | — |
| M-PCSAMP PC 采样 | `pc_sample_buf` | timer ISR 写 mepc | 拉取 + 归类 + flame graph | 单向↑ | — | — |
| M-CONFIG 热配置 | `dut_config_t` | 主循环检测 version 变化 | 写新 config + 翻 version | 单向↓ | — | — |
| M-BP 软断点 | 复用 `call_gate_t` | trap_hook 拦截 ebreak + 报现场 | patch 指令 + 等命中 + 恢复 | 双向 | — | ✓ |
| M-HOOK 函数 Hook | trampoline 区 | 编译期 hook 槽 | 写 trampoline 跳转 | 双向（构建期）| — | — |
| M-COREDUMP | 复用 `call_gate_t` + 段 | dispatcher 响应 + 关中断 + 写 TCB 列表 | 读全段 + 拼 ELF core | 双向 | ✓ | — |
| M-PATCH 热补丁 | `.text_patch` 区 | （被动）I-cache flush | 写 patch + 改 prologue 跳转 | 单向↓ | — | — |

### 5.2 .debug_region 共享内存布局（被测固件链接脚本固化）

```
0x10000000  ┌──────────────────────────┐  __debug_region_base
            │ call_gate_t              │  ← M-CALL / M-BP / M-COREDUMP 复用
0x10001000  ├──────────────────────────┤
            │ rtt_control_block_t      │  ← M-RTT
0x10002000  ├──────────────────────────┤
            │ rtt up_buf[3] + down_buf │
0x10006000  ├──────────────────────────┤
            │ trace_buf (events)       │  ← M-TRACE
0x10010000  ├──────────────────────────┤
            │ trace_meta (event 注册表)│  ← 编译期 .trace_meta section
0x10011000  ├──────────────────────────┤
            │ pc_sample_buf            │  ← M-PCSAMP
0x10012000  ├──────────────────────────┤
            │ crash_beacon_t           │  ← M-BEACON
0x10013000  ├──────────────────────────┤
            │ dut_config_t             │  ← M-CONFIG
0x10014000  ├──────────────────────────┤
            │ canary 区                │  ← M-CANARY（每 task 栈底）
0x10015000  ├──────────────────────────┤
            │ cov_counters             │  ← M-COV（编译期 .cov_counters）
0x10100000  ├──────────────────────────┤
            │ .text_patch（保留地址）  │  ← M-PATCH
0x10110000  └──────────────────────────┘
```

**所有地址桩 CPU 启动时通过 ELF 符号 `__debug_region_base` 一次性定位**，绝不写死。

### 5.3 被测固件交付物清单

#### 5.3.1 必须新增的源文件

| 文件 | 内容 | 谁写 |
|---|---|---|
| `dut_debug_contract.c` | RTOS 契约的实现（5 必选 + 1 可选） | **固件团队** |
| `dut_debug_region.c` | 共享内存段定义 + 链接锚点 | debug 库 |
| `dut_debug_dispatcher.c` | dispatcher_poll 实现，处理 CALL/BP/COREDUMP | debug 库 |
| `dut_debug_rtt.c` | RTT 写入 + dbginfo 重定向 | debug 库 |
| `dut_debug_trace.c` | TRACE 宏 + 事件注册 | debug 库 |
| `dut_debug_beacon.c` | trap_hook 实现（写 beacon） | debug 库 |
| `dut_debug_canary.c` | 金丝雀初始化（task 启动时挂） | debug 库 |
| `dut_debug_pcsamp.c` | timer ISR 中读 mepc 写 buf | debug 库 |
| `dut_debug_config.c` | config 版本号检测 + reload | debug 库 |

**被测侧**：debug 库一次性集成，固件团队仅写 `dut_debug_contract.c`（~50 行胶水）。

#### 5.3.2 链接脚本改动

```ld
/* dut.ld 新增段 */
SECTIONS {
    .debug_region 0x10000000 (NOLOAD) : {
        __debug_region_base = .;
        KEEP(*(.call_gate))
        . = ALIGN(4096);
        KEEP(*(.rtt_cb))
        KEEP(*(.rtt_buf))
        . = ALIGN(4096);
        KEEP(*(.trace_buf))
        KEEP(*(.trace_meta))
        . = ALIGN(4096);
        KEEP(*(.pc_sample))
        KEEP(*(.beacon))
        KEEP(*(.config))
        KEEP(*(.canary))
        KEEP(*(.cov_counters))
        __debug_region_end = .;
    } > RAM

    .text_patch 0x10100000 (NOLOAD) : {
        __text_patch_base = .;
        . += 0x10000;
    } > RAM
}
```

#### 5.3.3 编译开关与构建产物

```makefile
# 必须开（生产可保留）
CFLAGS += -DDUT_DEBUG_RTT=1
CFLAGS += -DDUT_DEBUG_BEACON=1
CFLAGS += -DDUT_DEBUG_CALL_GATE=1
CFLAGS += -DDUT_DEBUG_CONFIG=1
CFLAGS += -DDUT_DEBUG_CANARY=1

# Dev 版才开（高侵入或大开销）
ifdef DEV_BUILD
CFLAGS += -DDUT_DEBUG_TRACE=1
CFLAGS += -DDUT_DEBUG_PC_SAMPLE=1
CFLAGS += -DDUT_DEBUG_COVERAGE=1 -fprofile-arcs -ftest-coverage
CFLAGS += -DDUT_DEBUG_BREAKPOINT=1
CFLAGS += -fpatchable-function-entry=8     # 函数 hook 槽
endif
```

### 5.4 桩 CPU 库交付物清单

#### 5.4.1 源文件

| 文件 | 内容 |
|---|---|
| `dut_debug_client.h` | 公共 API 头 |
| `dut_debug_client.c` | API 实现，调用 `SUT_MemRead/Write/Wait` |
| `dut_symtab_loader.c` | 启动时解析 DUT.elf → 加载 `g_dut_symtab[]` 与 DWARF |
| `dut_rtt_pump.c` | 后台 task 拉 RTT，落盘 |
| `dut_trace_pump.c` | 后台 task 拉 trace，主机侧时间线归档 |
| `dut_pcsamp_pump.c` | 后台 task 拉 PC samples，生成 flame graph 数据 |
| `dut_beacon_watch.c` | 周期检查 beacon magic |
| `dut_canary_scan.c` | 周期 scan 金丝雀 |
| `dut_coredump_writer.c` | 调度 coredump + 输出 ELF core |

#### 5.4.2 公共 API（按机制分组）

```c
/* === 初始化 === */
ERRNO_T DUT_DebugInit(const char *elf_path);
ERRNO_T DUT_DebugStart(void);     /* 启动所有后台 pump */
ERRNO_T DUT_DebugStop(void);

/* === M-CALL 函数调用门 === */
ERRNO_T DUT_Call(const char *name, uint32_t argc, const uint64_t argv[8],
                 uint64_t *retval, uint32_t timeout_ms);

/* === M-WATCH 变量读写 === */
ERRNO_T DUT_VarRead (const char *name, void *out, uint32_t size);
ERRNO_T DUT_VarWrite(const char *name, const void *in, uint32_t size);
ERRNO_T DUT_WatchAdd(const char *name, uint32_t period_ms);

/* === M-RTT 日志 === */
ERRNO_T DUT_RttPoll      (uint32_t channel, uint8_t *out, uint32_t cap, uint32_t *outLen);
ERRNO_T DUT_RttDownWrite (uint32_t channel, const void *data, uint32_t len);

/* === M-TRACE 事件追踪 === */
ERRNO_T DUT_TraceEnable  (bool on);
ERRNO_T DUT_TracePoll    (trace_event_t *out, uint32_t cap, uint32_t *outCount);
ERRNO_T DUT_TraceFormat  (const trace_event_t *e, char *out, uint32_t cap);

/* === M-PCSAMP 性能采样 === */
ERRNO_T DUT_PcSampleEnable(bool on);
ERRNO_T DUT_PcSamplePoll  (uint32_t *out, uint32_t cap, uint32_t *outCount);
ERRNO_T DUT_PcSampleReport(const char *flamegraph_out_path);

/* === M-COV 覆盖率 === */
ERRNO_T DUT_CoverageDump  (const char *lcov_out_path);

/* === M-CANARY 栈检查 === */
ERRNO_T DUT_CanaryCheckAll(uint32_t *bad_count);

/* === M-BEACON crash 现场 === */
ERRNO_T DUT_BeaconRescue  (const char *artifact_dir);

/* === M-COREDUMP === */
ERRNO_T DUT_CoredumpRequest(const char *core_out_path);

/* === M-CONFIG 热配置 === */
ERRNO_T DUT_ConfigUpdate  (const dut_config_t *cfg);

/* === M-BP 软断点 === */
typedef void (*bp_callback_t)(uint32_t pc, const uint32_t regs[32], void *user);
ERRNO_T DUT_BreakpointSet (const char *func_name, bp_callback_t cb, void *user);
ERRNO_T DUT_BreakpointClear(const char *func_name);

/* === M-HOOK 函数 Hook === */
ERRNO_T DUT_HookInstall   (const char *func_name, uint32_t hook_addr);
ERRNO_T DUT_HookRemove    (const char *func_name);

/* === M-PATCH 热补丁 === */
ERRNO_T DUT_HotPatch      (const char *func_name, const void *patch_code, uint32_t code_len);
```

---

## 6. 实施优先级与路线图

### 6.1 难度评级标准

| 等级 | 判定标准 | 主要风险 |
|---|---|---|
| **★** | 桩侧实现，被测零侵入或仅一次性常量导出 | 几乎无 |
| **★★** | 被测主循环钩子 + 简单数据结构 / 链接脚本简单段 / dev 编译开关 | 低（功能局限） |
| **★★★** | trap handler 扩展 / dispatcher 协议 / ISR 安全 / 编译器插桩 | 中（边界条件、ISR 竞态） |
| **★★★★** | 修改代码段（`.text`） / I-cache 一致性 / 编译器深度特性 / trampoline | 高（写错就 crash 整片） |

### 6.2 全机制评估总表

按 价值 / (难度 × 估时) 综合排序：

| # | 机制（§） | 价值 | 难度 | 估时 | 关键依赖 | ROM / RAM |
|---|---|---|---|---|---|---|
| 1 | **3.11** Live Watch | 用例运行中实时看被测变量 | ★ | 1-2d | 仅桩侧 + 符号表 | 0 / 0 |
| 2 | **3.12a** 配置热更新 | 不重启调参 | ★ | 1-2d | 主循环钩子 | ~50B / ~50B |
| 3 | **3.2** RTT 高速日志 | 替代 UART，万能日志出口 | ★★ | 3-5d | 主循环 + 链接脚本 | ~500B / 64KB |
| 4 | **3.9** Crash Beacon | 任意 FAIL 必有现场 | ★★ | 3-5d | trap_hook | ~200B / ~512B |
| 5 | **3.7** 代码覆盖率 | 首用例准入硬指标 | ★★ | 3-5d | gcov 开关 + dev/release 双构建 | dev only |
| 6 | **3.8** 栈金丝雀 + 堆红区 | 静默 bug 早暴露 | ★★ | 3-5d | 链接脚本 + malloc wrapper | ~1KB / ~1KB |
| 7 | **3.6** PC 采样 | flame graph 性能分析 | ★★ | 2-4d | timer ISR + `mepc` | ~100B / ~16KB |
| 8 | **3.1** 函数调用门（引 6B）| 任意被测函数可调 | ★★★ | 5-8d | dispatcher + 参数序列化 | ~1KB / ~256B |
| 9 | **3.3** 环形事件追踪 | 时间线分析 + 性能 profile | ★★★ | 5-8d | dispatcher + cycle counter + ISR 安全 | ~1KB / ~64KB |
| 10 | **3.10** 按需 Coredump | 离线 GDB 调试 | ★★★ | 5-8d | dispatcher + TCB layout | ~500B / N×64KB |
| 11 | **3.5** 函数入口 Hook | 永久 trace / 错误注入 | ★★★ | 5-10d | GCC `patchable_function_entry` | 编译期 |
| 12 | **3.4** 软件断点 | 一次性断点定位 | ★★★★ | 8-15d | 写 `.text` + I-cache flush + trap dispatch | ~500B |
| 13 | **3.12b** 函数热补丁 | 不重启注入故障 / 修补 | ★★★★ | 10-20d | #12 + trampoline + patch 区预留 | ~2KB |

> **估时约定**：一个熟悉 RISC-V + 自研 RTOS 的工程师 0 → 验收的纯开发时间，含单测，不含跨团队协调和 hardware 排队。
>
> **3.12a / 3.12b**：§ 3.12 内含「配置热更（极简）」和「函数热补丁（高级）」两件事，难度差三级，单独评级。

### 6.3 阶段路线

**阶段 A — 首期必做（约 2-3 周）：** #1 #2 #3 #4 + #8 函数调用门
- **选择标准**：难度 ≤ ★★ 或属于"地基依赖"；覆盖"看现场 / 调参 / 调函数"三大基础诉求
- **完成后能力**：90% 定位场景有现成手段；后续机制都基于这层共享内存 + RTT 出口

**阶段 B — 按需开（约 3-4 周）：** #5 #6 #7 #9 #10
- **选择标准**：难度 ≤ ★★★，需阶段 A 的 RTT / Beacon 作日志出口
- **解锁场景**：性能 profile、内存破坏定位、离线 coredump 分析、覆盖率门禁

**阶段 C — 专家用（约 4-6 周）：** #11 #12 #13
- **选择标准**：难度 ★★★~★★★★，触及代码段 / 编译器特性 / I-cache 一致性
- **裁剪原则**：阶段 A/B 不足以支撑特定场景时才启动；可以永远不做

### 6.4 依赖图（自下而上）

```
基础层（6B）：.debug_region 共享内存 + 链接脚本固定地址
   │
   ├─ 桩侧拉取（无需被测代码）── #1 Live Watch
   │
   ├─ 主循环钩子 ────────────── #2 配置热更 / #3 RTT / #6 Canary
   │
   ├─ trap_hook ───────────────── #4 Crash Beacon
   │
   ├─ ISR 接入 ────────────────── #7 PC 采样 / #9 Tracing
   │
   ├─ dispatcher 协议 ─────────── #8 函数调用门 / #9 / #10 Coredump
   │
   ├─ 编译期插桩 ───────────────── #5 Coverage / #11 Hook
   │
   └─ 写 `.text` + I-cache flush ── #12 软断点 / #13 热补丁
```

向下依赖越深，难度评级越高，对自研 RTOS 契约（§ 4.1）的要求越严。

---

## 7. 待澄清清单

| ID | 问题 | 涉及 |
|---|---|---|
| Q-100 | 被测 FPGA MPU 是否允许写代码段？影响 § 3.4 / 3.5 / 3.12 | § 3.4 |
| Q-101 | 被测 FPGA 是否有 cycle counter 寄存器？影响时间戳精度 | § 3.3 / 3.6 |
| Q-102 | 被测固件是否有 trap handler 扩展点？影响 crash beacon 与软断点 | § 3.4 / 3.9 |
| Q-103 | 被测编译器版本是否支持 GCC `patchable_function_entry`？ | § 3.5 |
| Q-104 | 自研 RTOS 是否能满足 § 4.3 列出的 5 必选契约 + 1 可选 TCB layout？ | § 4.3 |
| Q-105 | I-cache flush 接口（cbo.flush.i / fence.i / 自定义）| § 3.4 / 3.5 |
| Q-106 | `.debug_region` 在 RAM 的固定地址 | § 4 |
| Q-107 | 是否允许 dev/release 双构建产物（功能编译开关）？ | § 4.3 |

---

## 附录：参考资料

### 业界工具与文档

- [SEGGER J-Link RTT — Real Time Transfer](https://www.segger.com/products/debug-probes/j-link/technology/about-real-time-transfer/) — 共享内存控制块 + 多通道环形缓冲，§ 3.2 模型
- [SEGGER RTT 知识库](https://kb.segger.com/RTT) — 内存布局、阻塞/非阻塞模式
- [SEGGER SystemView 持续记录](https://www.segger.com/products/development-tools/systemview/technology/continuous-recording/) — § 3.3 事件追踪可视化参考
- [Linux Kernel Probes (kprobes) 文档](https://docs.kernel.org/trace/kprobes.html) — § 3.4 软件断点：替换首字节为 trap 指令
- [ftrace — Function Tracer](https://www.kernel.org/doc/html/latest/trace/ftrace.html) — § 3.3 ring buffer 与 § 3.5 函数入口 patch
- [GDB Remote Serial Protocol HOWTO](https://www.embecosm.com/appnotes/ean4/embecosm-howto-rsp-server-ean4-issue-2.html) — § 3.4 协议形态参考
- [eBPF 介绍](https://ebpf.io/what-is-ebpf/) — 动态插桩思想，但不引入 BPF VM
- [minicoredumper — Creating Efficient Small Core Dump](https://tracingsummit.org/ts/2016/CoreDump/) — § 3.10 精简 coredump
- [Auterion embedded-debug-tools](https://github.com/Auterion/embedded-debug-tools) — Cortex-M debug & profiling 实战
- [A Survey of Embedded Software Profiling Techniques](https://arxiv.org/pdf/1312.2949) — § 3.6 / 3.7 综述
- [From Breakpoints to Tracepoints (Linux Kernel Tracing)](https://riptides.io/blog-post/from-breakpoints-to-tracepoints-an-introduction-to-linux-kernel-tracing) — § 3.4 → § 3.3 演进逻辑

### 与本仓库其他文档的交叉引用

- [子 wiki 6](./06_子wiki_Autotest软件架构.md) — 跨平台架构、PlatformAdapter
- [子 wiki 6B](./06b_子wiki_原型测试环境详设.md) — FPGA 平台落地详设、A/B 双交互机制、§ 3.11 Memory Invocation Gate
- [子 wiki 4](./04_子wiki_DFX告警寄存器查询.md) — 维测寄存器（与 § 3.9 Crash Beacon 互补：DFX 是硬件维测，beacon 是软件维测）
