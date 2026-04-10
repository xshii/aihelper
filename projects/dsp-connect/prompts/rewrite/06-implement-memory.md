# Step 6: 实现内存读写层

## Role
你是一个嵌入式调试工具开发者，熟悉内存访问抽象和地址空间转换。

## Task
实现 `src/memory/` 下的内存读写层代码。
这是传输层和架构层之间的薄胶水层。

## Context
内存层不是独立的大模块——它是一个薄的协调层，串联：
- **arch 层**：将 DWARF 逻辑地址转换为传输层需要的物理地址
- **transport 层**：实际执行内存读写
- **arch 层**（再次）：对读取的数据做字节序交换

调用链：`caller → mem_read → arch.logical_to_physical → transport.mem_read → arch.swap_endian → return`

## Refer to Demo
逐一阅读以下文件：
- `src/memory/memory.h` — 接口：`dsc_mem_read(transport, arch, logical_addr, buf, len)` 和 `dsc_mem_write`
- `src/memory/memory.c` — 实现：地址转换 + 分块传输 + 字节序交换
- `src/memory/memory_batch.h` / `.c` — 可选的批量读取

重点关注：
- 函数签名：接收 `dsc_transport_t *` 和 `const dsc_arch_t *`
- 大块读取的分块策略（chunk size）
- 字节序交换的时机：读取后交换，写入前交换

## Check Inventory
打开 Inventory JSON，确认：
1. 现有代码的内存读写是否有特殊逻辑（如对齐要求、最大传输大小）
2. 是否有 batch/burst 读取需求
3. 是否有内存映射缓存（memory-mapped cache）

## Rules
1. DO: 严格按照 demo 的函数签名实现
2. DO: 先做地址转换，再调传输层
3. DO: 读取后做字节序交换，写入前做字节序交换
4. DO: 处理大块读取的分块（如果 transport 有最大单次传输限制）
5. DO: 每个函数不超过 50 行
6. DON'T: 不要在内存层缓存数据——每次都实际读取
7. DON'T: 不要修改 `memory.h` 中的接口
8. DON'T: 不要直接操作 socket 或文件——全部通过 transport vtable
9. NEVER: 不要跳过字节序交换——即使当前目标恰好是 little-endian
10. ALWAYS: 验证 len > 0 和 buf != NULL

## Steps

### 6.1 实现 dsc_mem_read()
按以下流程实现：

```
1. 参数检查（transport, arch, buf 非 NULL；len > 0）
2. logical_to_physical(arch, logical_addr) → physical_addr
3. if len > MAX_CHUNK:
     分块读取，每块 MAX_CHUNK 字节
   else:
     单次读取
4. transport.mem_read(physical_addr, buf, len)
5. swap_endian(arch, buf, element_size)  // 按字大小交换
6. 返回结果
```

分块读取的关键：
```c
#define MEM_MAX_CHUNK 256  /* 单次最大传输字节数 */

static int read_chunked(dsc_transport_t *tp, uint64_t phys_addr,
                        void *buf, size_t len)
{
    uint8_t *p = (uint8_t *)buf;
    size_t remaining = len;
    uint64_t addr = phys_addr;

    while (remaining > 0) {
        size_t chunk = (remaining > MEM_MAX_CHUNK) ? MEM_MAX_CHUNK : remaining;
        int rc = dsc_transport_mem_read(tp, addr, p, chunk);
        if (rc < 0) return rc;
        p += chunk;
        addr += chunk;
        remaining -= chunk;
    }
    return DSC_OK;
}
```

### 6.2 实现 dsc_mem_write()
与 read 镜像，但字节序交换在写入前：

```
1. 参数检查
2. logical_to_physical(arch, logical_addr) → physical_addr
3. 复制 buf 到临时缓冲区（不修改调用者数据）
4. swap_endian(arch, temp_buf, element_size)  // 写入前交换
5. if len > MAX_CHUNK:
     分块写入
   else:
     单次写入
6. transport.mem_write(physical_addr, temp_buf, len)
7. 返回结果
```

### 6.3 可选：实现 memory_batch（批量读取）
如果 Inventory 表明需要批量读取（如一次读多个变量）：
- 实现收集多个 read 请求 → 合并相邻地址 → 减少传输次数
- 如果 Inventory 标记为 `remove`，创建空桩文件

## Output Format
产出以下文件：
- `memory.c` — 核心读写实现
- `memory_batch.c` — 批量读取（如果需要）

```c
/* PURPOSE: Arch-aware memory read/write — 地址转换 + 字节序交换 + 分块传输
 * PATTERN: 薄胶水层 — 串联 arch 和 transport，不持有任何状态
 * FOR: 弱 AI 参考如何在传输层之上构建内存访问抽象 */
```

## Quality Checklist
- [ ] `dsc_mem_read` 完成三步：地址转换 → 传输层读取 → 字节序交换
- [ ] `dsc_mem_write` 完成三步：地址转换 → 字节序交换 → 传输层写入
- [ ] 大块数据正确分块处理
- [ ] 写入不修改调用者传入的 buf（使用临时缓冲区）
- [ ] 所有参数做 NULL 检查
- [ ] 分块读取时地址正确递增
- [ ] 错误码来自 `dsc_errors.h`
- [ ] 每个函数不超过 50 行
- [ ] 没有直接操作 socket 或文件描述符

## Edge Cases
- 如果 len 为 0，直接返回 `DSC_OK`（不调用传输层）
- 如果地址转换失败（溢出），传播错误码
- 如果传输层在分块读取的中间失败，返回错误（不尝试重试——重试是传输层的事）
- 如果字大小不整除 len，处理尾部字节（可能需要读一个完整字再截取）

## When Unsure
- **不确定最大分块大小？** 使用 256 字节，在注释中标注这是可调参数
- **不确定字节序交换的粒度？** 使用 `arch.word_size()` 返回的值
- **不确定写入是否需要临时缓冲区？** 需要——永远不修改调用者数据
- **不确定地址对齐要求？** 查 discover chain Step 5。默认无对齐要求
