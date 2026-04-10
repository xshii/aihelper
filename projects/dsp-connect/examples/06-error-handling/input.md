# Example 6: 错误处理

## 场景

各种错误情况下的行为。

## 操作与预期

```c
// 1. 符号不存在
int rc = dsc_read_var(ctx, "nonexistent_var", buf, sizeof(buf));
// rc = DSC_ERR_NOT_FOUND (-3)
// dsc_last_error(ctx) → "resolve 'nonexistent_var': symbol not found"

// 2. 连接超时
// (目标板未响应)
rc = dsc_read_var(ctx, "g_counter", buf, sizeof(buf));
// rc = DSC_ERR_TRANSPORT_TIMEOUT (-42)
// dsc_last_error(ctx) → "mem_read @0x20000100: transport timeout"

// 3. 输出缓冲区太小
char tiny[8];
rc = dsc_read_var(ctx, "g_config", tiny, sizeof(tiny));
// rc = DSC_ERR_INVALID_ARG (-2)
// dsc_last_error(ctx) → "output buffer too small: need 256, have 8"

// 4. ELF 文件无调试信息
dsc_context_t *ctx2 = dsc_open(&(dsc_open_params_t){
    .elf_path = "stripped.elf",  // 无 DWARF
    .transport = "telnet", .arch = "byte_le",
    .host = "192.168.1.100", .port = 4444,
});
// ctx2 = NULL (打开失败)
// 日志输出: "[ERROR] DWARF open failed: ELF has no debug info"
```
