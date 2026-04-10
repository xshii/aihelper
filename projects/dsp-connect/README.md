# dsp-connect

符号级内存查看器——嵌入式/DSP 设备软件调试（软调）框架。

## 它做什么

```
ELF 文件 + 变量名  ──►  连接设备  ──►  读取内存  ──►  格式化显示
  (DWARF)                (telnet)        (地址转换)      (类型解析)
```

一行代码读取远程设备上的变量：

```c
dsc_context_t *ctx = dsc_open(&(dsc_open_params_t){
    .elf_path  = "firmware.elf",
    .transport = "telnet",
    .arch      = "byte_le",
    .host      = "192.168.1.100",
    .port      = 4444,
});

char buf[4096];
dsc_read_var(ctx, "g_config.network.ip", buf, sizeof(buf));
printf("%s\n", buf);
// → g_config.network.ip = 3232235876 (0xC0A80164)

dsc_close(ctx);
```

## 构建

```bash
cmake -B build                    # 配置
cmake --build build               # 编译
ctest --test-dir build            # 运行测试

# Debug 模式 + compile_commands.json（给 clangd / VSCode）
cmake -B build -DCMAKE_BUILD_TYPE=Debug -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
```

## 架构

分层设计，严格自顶向下依赖：

```
Layer 0 API:   dsc_read_var(ctx, "varname")       ← 用户只需这一行
  ├── Core:    上下文管理 + 管线编排
  ├── Resolve: 变量路径 → 地址 + 类型
  ├── Memory:  地址转换 + 传输读写
  ├── Format:  裸字节 → 可读输出
  ├── DWARF:   ELF 调试信息解析
  ├── Transport: 设备连接（telnet/serial/shm）     ← 工厂模式，可扩展
  └── Arch:    架构适配（字节/字寻址、字节序）       ← 工厂模式，可扩展
```

## 本项目的用途

这是一个 **demo 参考实现**，用于：

1. **弱 AI 学习** — 作为代码模板供弱 AI 模仿重写
2. **Prompt 驱动** — 配套 4 条 prompt 链引导弱 AI 完成代码迁移
3. **工厂模式扩展** — 新硬件只需添加 transport/arch 适配器

详见 [PROMPT.md](PROMPT.md) 了解完整的 prompt 链结构。

## 目录结构

```
dsp-connect/
├── src/              # C 参考实现
│   ├── util/         # 基础设施
│   ├── dwarf/        # DWARF 解析
│   ├── transport/    # 传输层（telnet/serial/shm）
│   ├── arch/         # 架构适配
│   ├── resolve/      # 符号解析
│   ├── memory/       # 内存读写
│   ├── format/       # 格式化显示
│   └── core/         # 胶水层
├── tests/            # 测试套件（含 mock）
├── prompts/          # Prompt 链
│   ├── discover/     # 盘点现有代码
│   ├── rewrite/      # 按 demo 重写
│   ├── validate/     # 验证新旧一致
│   └── adapt/        # 适配新架构
├── DESIGN.md         # 架构设计文档
├── PROMPT.md         # Prompt 索引
└── SKILL.md          # 技能定义
```
