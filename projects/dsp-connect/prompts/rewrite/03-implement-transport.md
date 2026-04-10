# Step 3: 实现通信传输层

## Role
你是一个嵌入式通信工程师，熟悉 telnet/serial/TCP 协议和 C 语言 socket 编程。

## Task
实现 `src/transport/` 下的传输层代码。严格使用 demo 的 vtable 模式。
只实现 Inventory 中标记为 `keep` 的传输方式。

## Context
传输层负责与目标设备通信（读写内存）。dsp-connect demo 定义了一个抽象接口
（`dsc_transport_ops` vtable），每种具体传输方式（telnet/serial/shm）实现这个接口。
工厂模式（`transport_factory`）负责按名称创建具体实例。

现有 C++ 代码的传输层可能：
- 使用类继承而非 vtable
- 有自定义的命令协议（discover chain Step 3 记录了具体格式）
- 包含从未使用的传输方式

## Refer to Demo
逐一阅读以下文件：
- `src/transport/transport.h` — vtable 定义：`dsc_transport_ops`（open/close/mem_read/mem_write/exec_cmd/destroy）
- `src/transport/transport_factory.h` — 工厂注册模式：`dsc_transport_register` + `DSC_TRANSPORT_REGISTER` 宏
- `src/transport/transport_factory.c` — 工厂实现：静态注册表
- `src/transport/transport_telnet.h` / `.c` — telnet 实现示例
- `src/transport/transport_serial.h` / `.c` — serial 实现示例
- `src/transport/transport_shm.h` / `.c` — shm 实现示例

重点关注：
- vtable 的函数签名和语义
- 具体传输如何嵌入 `dsc_transport_t` 作为第一个成员
- `DSC_TRANSPORT_REGISTER` 宏如何实现自动注册
- inline wrapper 函数如何分发到 vtable

## Check Inventory
打开 Inventory JSON，定位通信层模块：
1. 确认哪些传输方式标记为 `keep`（必须实现）
2. 确认哪些传输方式标记为 `remove`（不创建文件）
3. 确认 discover chain Step 3 记录的命令格式（读/写内存的具体协议）

## Rules
1. DO: 每个具体传输 struct 的第一个成员必须是 `dsc_transport_t`
2. DO: 使用 `DSC_TRANSPORT_REGISTER` 宏实现自动注册
3. DO: 从 discover chain Step 3 的输出中复制精确的命令格式
4. DO: 实现完整的错误处理（连接失败、超时、命令解析错误）
5. DO: 每个函数不超过 50 行
6. DON'T: 不要修改 `transport.h` 中的 vtable 定义
7. DON'T: 不要实现 Inventory 中 `remove` 的传输方式
8. DON'T: 不要添加 demo vtable 中没有的操作（如 reset、flush）
9. NEVER: 不要自己发明命令协议——必须使用 discover chain 记录的格式
10. ALWAYS: 在 `exec_cmd` 实现中处理响应超时

## Steps

### 3.1 实现 transport_factory.c
1. 定义静态注册表数组（名称 + 构造函数指针）
2. 实现 `dsc_transport_register()` — 添加到注册表
3. 实现 `dsc_transport_create()` — 按名称查找并调用构造函数
4. 实现 `dsc_transport_free()` — close + destroy 便捷函数
5. 实现 `dsc_transport_list()` — 列出已注册的名称

### 3.2 实现主要传输方式（通常是 telnet）
按以下结构实现：

```c
/* 私有结构体 — 第一个成员是 dsc_transport_t */
typedef struct {
    dsc_transport_t  base;       /* MUST be first member */
    int              sockfd;     /* TCP socket fd */
    char             host[256];
    int              port;
    int              timeout_ms;
    /* ... 其他私有状态 */
} telnet_transport_t;
```

实现 vtable 的每个函数：

| 函数 | 职责 | 关键细节 |
|------|------|---------|
| `open` | 建立 TCP 连接 | 使用 `connect()` + 超时处理 |
| `close` | 关闭连接 | 关闭 socket |
| `mem_read` | 读内存 | 发送读命令（从 discover 获取格式）→ 解析响应 |
| `mem_write` | 写内存 | 发送写命令（从 discover 获取格式）→ 确认响应 |
| `exec_cmd` | 执行通用命令 | 发送文本命令 → 读取文本响应 |
| `destroy` | 释放资源 | free 整个 struct |

### 3.3 命令格式适配
从 discover chain Step 3 的输出中提取：
- **读内存命令**: 例如 `md <addr_hex> <length>` → 解析返回的十六进制数据
- **写内存命令**: 例如 `mw <addr_hex> <value_hex>` → 解析确认响应
- **响应解析**: 使用 `sscanf` 或手动解析，处理前缀/后缀/分隔符

将命令格式定义为常量或 helper 函数：
```c
/* 读命令格式（从 discover chain Step 3 获取） */
static int format_read_cmd(char *buf, size_t buflen,
                           uint64_t addr, size_t len)
{
    return snprintf(buf, buflen, "md 0x%llx %zu",
                    (unsigned long long)addr, len);
}
```

### 3.4 实现其他 keep 的传输方式
对 Inventory 中每个标记为 `keep` 的传输方式，重复 3.2 的模式。

### 3.5 跳过 remove 的传输方式
对 Inventory 中标记为 `remove` 的传输方式：
- 不创建 `.h` / `.c` 文件
- 在 `transport_factory.c` 中不注册

## Output Format
每个传输方式产出两个文件（`.h` + `.c`），加上工厂实现。

对于跳过的传输方式，在 `transport_factory.c` 中添加注释：
```c
/* SKIPPED: transport_jtag — Inventory status: remove
 * Reason: 不再使用 JTAG 连接方式 */
```

## Quality Checklist
- [ ] 每个具体传输 struct 的第一个成员是 `dsc_transport_t`
- [ ] 所有 vtable 函数都有实现（即使某些是空操作）
- [ ] `DSC_TRANSPORT_REGISTER` 宏正确使用
- [ ] 命令格式与 discover chain Step 3 的记录一致
- [ ] 读命令的响应解析处理了所有字段
- [ ] 超时处理：connect 超时、recv 超时、send 超时
- [ ] 错误返回使用 `dsc_errors.h` 中定义的错误码
- [ ] 每个函数不超过 50 行
- [ ] Inventory 中 `remove` 的传输方式没有代码
- [ ] socket 在所有错误路径上正确关闭

## Edge Cases
- 如果 discover chain 记录的命令格式有多种变体（不同固件版本），实现最新/最常用的那种
- 如果现有代码有连接重试逻辑，在 `open` 中实现（最多 3 次，间隔 1s/2s/4s）
- 如果读取大块内存，`mem_read` 可能需要分块——参考 discover chain 中的最大单次读取大小
- 如果 telnet 协议有 IAC 转义（0xFF），必须处理

## When Unsure
- **不确定命令格式？** 使用 discover chain Step 3 的输出。如果 discover 也没有记录，标记 `[NEEDS_HUMAN_REVIEW]`
- **不确定超时值？** 使用 5000ms 作为默认值
- **不确定响应解析规则？** 写一个宽松的解析器（允许额外空白），在注释中说明假设
- **不确定是否需要 TLS/加密？** 不需要——软调是内网工具
