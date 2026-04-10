# Example 1: 读取一个简单全局变量

## 场景

固件 ELF 文件中有一个全局变量：

```c
// 固件源码
uint32_t g_counter = 42;
```

目标板通过 telnet 连接（192.168.1.100:4444），字节寻址，小端。

## 操作

```c
dsc_context_t *ctx = dsc_open(&(dsc_open_params_t){
    .elf_path  = "firmware.elf",
    .transport = "telnet",
    .arch      = "byte_le",
    .host      = "192.168.1.100",
    .port      = 4444,
});

char buf[256];
dsc_read_var(ctx, "g_counter", buf, sizeof(buf));
printf("%s\n", buf);

dsc_close(ctx);
```

## 内部过程

1. **Resolve**: 在 DWARF 中查找 `g_counter` → addr=0x20000100, type=uint32_t, size=4
2. **Memory**: telnet 发送 `md 0x20000100 4` → 收到 `2a 00 00 00`
3. **Format**: 小端解析 → 42, 格式化为 `42 (0x0000002A)`
