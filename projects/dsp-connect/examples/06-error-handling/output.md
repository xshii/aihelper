# Expected Behavior

## 错误处理原则

1. **永远不 crash** — 任何错误都返回负数错误码，不会 segfault 或 abort
2. **错误信息具体** — `dsc_last_error()` 返回人类可读的描述，包含变量名/地址等上下文
3. **部分失败不感染** — 一个变量读取失败不影响后续读取
4. **资源安全** — 错误路径上所有资源都被正确释放

## 错误码速查

| 错误码 | 值 | 含义 | 常见原因 |
|--------|-----|------|---------|
| DSC_OK | 0 | 成功 | — |
| DSC_ERR_NOT_FOUND | -3 | 符号未找到 | 变量名拼写错误、ELF 版本不匹配 |
| DSC_ERR_TRANSPORT_TIMEOUT | -42 | 通信超时 | 目标板未启动、网络不通 |
| DSC_ERR_INVALID_ARG | -2 | 参数错误 | 缓冲区太小、NULL 指针 |
| DSC_ERR_DWARF_NO_DEBUG | -14 | 无调试信息 | ELF 被 strip、编译时未加 -g |

---

**Why this design:**
- 用返回值表示错误（C 惯例），不用 errno 或异常
- `dsc_last_error()` 提供人类可读消息，避免调用者自己拼装错误信息
- 错误码是负数，成功是 0——可以用 `if (rc < 0)` 统一检查
