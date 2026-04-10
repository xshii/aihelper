# Step 8: 实现核心集成层

## Role
你是一个软件架构师，擅长将多个子系统组装为一个统一的外观（Facade）API。

## Task
实现 `src/core/` 下的核心集成层代码。
将 Step 2-7 实现的所有子系统（dwarf、transport、arch、resolve、memory、format）
组装为 `dsc.h` 定义的公开 API。

## Context
核心层是整个库的顶层胶水代码。它：
1. 持有所有子系统的句柄（在 `dsc_context_t` 结构体中）
2. 管理初始化和释放的生命周期
3. 将公开 API 调用转化为子系统间的协作链

**不要在核心层实现业务逻辑。** 每个公开函数应该是一系列子系统调用的编排。

典型调用链：
```
dsc_read_var("g_config.mode", buf, len)
  → resolve("g_config.mode") → {addr, size, type}
  → mem_read(addr, raw_buf, size)
  → format(raw_buf, size, type) → formatted string
  → copy to buf
```

## Refer to Demo
**这是最重要的参考文件——请逐行阅读：**
- `src/core/dsc.h` — 公开 API 定义
- `src/core/dsc.c` — 完整的实现参考
- `src/core/dsc_errors.h` — 错误码定义
- `src/core/dsc_errors.c` — 错误码→字符串映射

重点关注 `dsc.c` 中的：
- `dsc_context_t` 结构体：持有哪些子系统句柄
- `dsc_open()` 的初始化顺序：dwarf → arch → transport → cache
- `dsc_close()` 的释放顺序（reverse）
- `read_var_core()` 的调用链：resolve → mem_read → format
- `set_error()` 的错误记录方式
- `cleanup_partial()` 的部分初始化失败处理
- `dsc_reload()` 的热重载逻辑

## Check Inventory
打开 Inventory JSON，确认：
1. 现有代码的 API 有哪些功能是 Inventory 标记为 `keep` 的
2. 是否有 demo 中没有的 API（如 batch read、variable watch、breakpoint）
3. 这些额外 API 的 keep/remove/uncertain 状态

## Rules
1. DO: 严格实现 `dsc.h` 中声明的所有函数
2. DO: 按 demo 的 `dsc.c` 的结构组织代码
3. DO: 每个 public 函数先做参数验证，再调子系统
4. DO: 每个函数不超过 50 行——拆分为 `static` helper
5. DO: 所有错误路径调用 `set_error()` 记录详细信息
6. DON'T: 不要在核心层实现业务逻辑——只做编排
7. DON'T: 不要修改 `dsc.h` 中的 API 定义
8. DON'T: 不要添加 `dsc.h` 中没有声明的公开函数
9. NEVER: 不要在部分初始化失败后泄漏资源——必须有 cleanup_partial
10. ALWAYS: `dsc_close(NULL)` 必须安全（空操作）

## Steps

### 8.1 实现 dsc_errors.c
1. 定义错误码→字符串映射表
2. 实现 `dsc_strerror()` — 返回错误码的描述

### 8.2 定义 dsc_context_t
参考 demo，包含：

```c
struct dsc_context_t {
    dsc_dwarf_t         *dwarf;
    dsc_symtab_t         symtab;
    dsc_transport_t     *transport;
    dsc_arch_t          *arch;
    dsc_resolve_cache_t *cache;
    char                *elf_path;
    char                 last_error[512];
};
```

### 8.3 实现初始化链（dsc_open）
严格按以下顺序初始化，任何一步失败都调用 cleanup_partial：

```
1. validate_params(params)  — 检查必填字段
2. alloc_context(elf_path)  — calloc + strdup
3. open_dwarf(ctx)          — dwarf_open + load_symbols
4. create_arch(ctx, name)   — arch_create
5. open_transport(ctx, p)   — transport_create + transport_open
6. create_cache(ctx)        — resolve_cache_create
```

每一步拆分为独立的 `static` 函数（和 demo 一样）。

### 8.4 实现释放链（dsc_close）
按初始化的反向顺序释放：

```
1. resolve_cache_destroy
2. transport_close + transport_destroy
3. arch_destroy
4. dwarf_close
5. symtab_free
6. free(elf_path)
7. free(ctx)
```

### 8.5 实现 read_var 调用链
参考 demo 的 `read_var_core()`：

```
1. resolve_var(ctx, path) → dsc_resolved_t {addr, size, type}
2. read_var_bytes(ctx, resolved, buf, size) → raw data
3. format_var(ctx, raw_data, size, type, opts, out, out_len) → formatted string
```

注意：
- 小变量用栈缓冲区（4096 字节），大变量 malloc
- 格式化后复制到输出缓冲区，检查长度
- heap 分配的临时缓冲区必须释放

### 8.6 实现 raw memory API
`dsc_read_mem()` 和 `dsc_write_mem()` 直接代理到 memory 层：

```c
int dsc_read_mem(dsc_context_t *ctx, uint64_t addr, void *buf, size_t len)
{
    if (!ctx || !buf || len == 0) return DSC_ERR_INVALID_ARG;
    int rc = dsc_mem_read(ctx->transport, ctx->arch, addr, buf, len);
    if (rc < 0) set_error(ctx, "read_mem @0x%llx: %s", ...);
    return rc;
}
```

### 8.7 实现 dsc_reload
热重载逻辑（ELF 文件更新后重新加载符号）：

```
1. close_dwarf(ctx)           — 关闭旧 DWARF 数据
2. cache_invalidate(ctx)      — 清空解析缓存
3. open_dwarf(ctx)            — 重新打开 ELF + 加载符号
4. 传输层保持连接不断
```

## Output Format
产出以下文件：
- `dsc.c` — 核心实现（最重要的文件）
- `dsc_errors.c` — 错误码实现

```c
/* PURPOSE: Core glue layer — 将所有子系统组装为统一 API
 * PATTERN: Facade — 一个 context 持有所有子系统句柄，公开函数编排调用链
 * FOR: 弱 AI 参考如何构建顶层集成层 */
```

## Quality Checklist
- [ ] `dsc.h` 中声明的每个函数都有实现
- [ ] `dsc_open` 的初始化顺序与 demo 一致
- [ ] `dsc_close` 的释放顺序是初始化的逆序
- [ ] 部分初始化失败时 `cleanup_partial` 正确释放已分配的资源
- [ ] `dsc_close(NULL)` 安全返回
- [ ] `dsc_read_var` 的调用链完整：resolve → mem_read → format
- [ ] 所有错误路径调用 `set_error()` 记录详细信息
- [ ] `dsc_reload` 不断开传输连接
- [ ] 每个函数不超过 50 行
- [ ] 没有资源泄漏（每个 malloc 都有对应的 free）
- [ ] 大变量读取使用 heap 缓冲区，用完释放

## Edge Cases
- 如果 `dsc_open` 的 transport 名称不存在，返回 NULL 并记录错误
- 如果 `dsc_reload` 时新 ELF 有不同的符号集，缓存自动清空
- 如果 `dsc_read_var` 的变量不存在，返回 `DSC_ERR_NOT_FOUND`
- 如果输出缓冲区太小，返回 `DSC_ERR_INVALID_ARG` 并记录需要的大小

## When Unsure
- **不确定初始化顺序？** 严格照搬 demo 的 `dsc.c`
- **不确定错误码用哪个？** 查 `dsc_errors.h`，选最匹配的
- **不确定是否需要额外的 public API？** 不需要——只实现 `dsc.h` 中声明的
- **不确定 cleanup_partial 是否覆盖了所有情况？** 用 NULL 检查保护每个 destroy 调用
