# Test Fixtures

## types_fixture.c

包含所有需要测试的 DWARF 类型的 C 源文件。在 Linux 上编译生成 ELF fixture：

```bash
gcc -g -O0 -o types_fixture.elf types_fixture.c
```

生成的 ELF 可用于 DWARF 解析器的集成测试。

注意：macOS 上 gcc 生成 Mach-O 格式（不是 ELF），需要交叉编译或在 Linux 上生成。
