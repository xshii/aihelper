# dsp-connect Architecture Design

## Overview

dsp-connect 是一个符号级内存查看器，用于嵌入式/DSP 设备的软件调试（软调）。

```
ELF File ──► DWARF Parser ──► Symbol Resolver ──► Memory Reader ──► Type Formatter ──► Output
                                     │                   │
                                     │              Transport Layer
                                     │              (telnet/serial/shm)
                                     │
                                Arch Adapter
                            (byte/word addressing)
```

## Layered Architecture

```
┌─────────────────────────────────────────────────────┐
│  Layer 0 API:  dsc_read_var(ctx, "g_config.mode")   │  ← 一行调用，零配置
├─────────────────────────────────────────────────────┤
│  Core:     dsc_context_t — 生命周期管理 + 管线编排    │
├──────────┬──────────┬───────────┬───────────────────┤
│ Resolve  │  Memory  │  Format   │  ← 功能层          │
├──────────┴──────────┴───────────┤                    │
│  DWARF Parser (libdwarf)        │  ← 数据层          │
├─────────────┬───────────────────┤                    │
│  Transport  │  Arch Adapter     │  ← 适配层          │
├─────────────┴───────────────────┤                    │
│  Util: hashmap, strbuf, log     │  ← 基础设施        │
└─────────────────────────────────┘
```

### Layer Dependencies (strict top-down, no cycles)

```
core → resolve, memory, format
resolve → dwarf
memory → transport, arch
format → dwarf (for type info)
dwarf → util
transport → util
arch → util
```

## Progressive Disclosure

| Layer | User Sees | Knowledge Required |
|-------|-----------|-------------------|
| **0** | `dsc_read_var(ctx, "varname")` | 只需知道变量名 |
| **1** | `dsc_read_var_ex(ctx, "varname", &opts)` | 可选：格式、深度、基数 |
| **2** | `dsc_context_config_t` + config file | 可选：缓存策略、超时、日志级别 |
| **3** | 自定义 `dsc_transport_t` / `dsc_arch_t` | 需要理解 vtable 接口 |

## Design Patterns

### Factory Pattern (Transport + Arch)
```c
// 通过名字创建，不需要知道具体实现
dsc_transport_t *tp = dsc_transport_create("telnet", &cfg);
dsc_arch_t *arch = dsc_arch_create("word24", &cfg);
```

### Strategy Pattern (vtable)
```c
// 所有 transport 共享同一接口
struct dsc_transport_t {
    int  (*open)(dsc_transport_t *self);
    void (*close)(dsc_transport_t *self);
    int  (*mem_read)(dsc_transport_t *self, uint64_t addr, void *buf, size_t len);
    int  (*mem_write)(dsc_transport_t *self, uint64_t addr, const void *buf, size_t len);
};
```

### Builder Pattern (Context)
```c
dsc_context_t *ctx = dsc_open(&(dsc_open_params_t){
    .elf_path = "firmware.elf",
    .transport = "telnet",
    .transport_host = "192.168.1.100",
    .transport_port = 4444,
    .arch = "byte_le",
});
```

## Data Flow: dsc_read_var("g_config.mode")

```
1. Resolve:   "g_config.mode"
              → lookup "g_config" in symbol table → addr=0x20001000, type=config_t
              → walk ".mode" in config_t fields → offset=+8, type=uint32_t
              → result: addr=0x20001008, type=uint32_t, size=4

2. Memory:    read 4 bytes from 0x20001008
              → arch.translate_addr(0x20001008) → physical address
              → transport.mem_read(phys_addr, buf, 4)
              → arch.swap_endian(buf, 4)
              → result: raw bytes [0x03, 0x00, 0x00, 0x00]

3. Format:    format uint32_t from raw bytes
              → "g_config.mode = 3 (0x00000003)"
```

## Error Handling Strategy

Every function returns `int` (0=success, negative=error). Error context stored in `dsc_context_t`:

```c
int rc = dsc_read_var(ctx, "nonexistent", &result);
if (rc != DSC_OK) {
    printf("Error: %s\n", dsc_strerror(ctx));
    // "Symbol 'nonexistent' not found in ELF debug info"
}
```

## Module Boundary Rules

1. **No cross-layer includes** — format/ never includes transport/
2. **Public API = one header** — each module exposes exactly one .h
3. **Private state via opaque pointers** — users see `dsc_context_t*`, not its fields
4. **All allocation via context** — no hidden malloc, caller controls lifetime
