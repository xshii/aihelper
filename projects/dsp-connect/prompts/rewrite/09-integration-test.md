# Step 9: 编写集成测试

## Role
你是一个测试工程师，擅长为嵌入式调试工具编写端到端测试。

## Task
为 Step 1-8 实现的完整代码库编写集成测试。
验证从 `dsc_open()` 到 `dsc_read_var()` 的完整调用链。

## Context
集成测试的目标是验证所有子系统正确协作。
单元测试在各步骤中已经覆盖了子系统内部逻辑。
集成测试关注的是**子系统之间的接口**是否正确对接。

测试分为两类：
1. **Mock 测试**：使用 mock transport（不需要真实设备）
2. **真机测试**：连接真实设备（如果有）

优先写 mock 测试——它们可以在 CI 中运行。

## Refer to Demo
阅读以下文件：
- `tests/` 目录下的所有测试文件（如果存在）
- `src/transport/transport_shm.c` — shm transport 可以用作 mock（读写本地内存）
- `src/core/dsc.h` — 公开 API（测试的入口）

## Check Inventory
打开 Inventory JSON，确认：
1. 哪些功能标记为 `keep`（必须测试）
2. 哪些功能标记为 `remove`（不需要测试）
3. 测试用例应覆盖 Inventory 中所有 `keep` 功能

## Rules
1. DO: 为每个公开 API 函数至少写一个 happy-path 测试
2. DO: 为每个公开 API 函数至少写一个 error-path 测试
3. DO: 使用 mock transport 避免依赖真实设备
4. DO: 测试函数命名格式：`test_<module>_<scenario>`
5. DO: 每个测试函数只测一件事
6. DO: 每个测试函数不超过 50 行
7. DON'T: 不要测试 Inventory 中 `remove` 的功能
8. DON'T: 不要在测试中使用全局状态——每个测试独立 setup/teardown
9. NEVER: 不要跳过错误路径测试——边界情况的 bug 最多
10. ALWAYS: 测试结束后释放所有资源（无泄漏）

## Steps

### 9.1 创建 Mock Transport
基于 shm transport 模式，创建一个内存中的 mock transport：

```c
/* PURPOSE: Mock transport — 用于测试，读写进程内存而非真实设备
 * PATTERN: 预填充一块内存，transport 读写操作直接作用于这块内存 */

typedef struct {
    dsc_transport_t  base;
    uint8_t         *memory;     /* 模拟设备内存 */
    size_t           mem_size;
    uint64_t         base_addr;  /* 内存起始地址 */
} mock_transport_t;
```

mock transport 的 `mem_read` 和 `mem_write` 直接操作 `memory` 数组。
不需要网络、socket、连接建立。

### 9.2 创建测试 ELF 文件
准备一个最小的 ELF 文件，包含以下全局变量：

```c
/* test_data.c — 编译为 test_data.elf */
#include <stdint.h>

int32_t g_counter = 42;

struct config_t {
    int32_t mode;
    float   gain;
    struct {
        uint16_t port;
        uint8_t  enabled;
    } network;
} g_config = { .mode = 1, .gain = 3.14f, .network = { .port = 8080, .enabled = 1 } };

int16_t g_buffer[8] = { 100, 200, 300, 400, 500, 600, 700, 800 };

typedef enum { STATE_IDLE = 0, STATE_RUN = 1, STATE_ERROR = 2 } state_t;
state_t g_state = STATE_RUN;
```

编译：`gcc -g -c test_data.c -o test_data.o && ld -r test_data.o -o test_data.elf`

### 9.3 编写 Happy-Path 测试

#### 测试组 1: 生命周期
```c
void test_open_close_basic(void)
{
    /* Setup: mock transport + test ELF */
    dsc_context_t *ctx = dsc_open(&params);
    assert(ctx != NULL);
    dsc_close(ctx);  /* 不崩溃 */
}

void test_close_null_safe(void)
{
    dsc_close(NULL);  /* 不崩溃 */
}
```

#### 测试组 2: 简单变量读取
```c
void test_read_simple_int(void)
{
    /* 预填充 mock 内存：在 g_counter 的地址写入 42 */
    char buf[256];
    int rc = dsc_read_var(ctx, "g_counter", buf, sizeof(buf));
    assert(rc == DSC_OK);
    assert(strcmp(buf, "42") == 0);
}
```

#### 测试组 3: Struct 成员读取
```c
void test_read_struct_member(void)
{
    char buf[256];
    int rc = dsc_read_var(ctx, "g_config.mode", buf, sizeof(buf));
    assert(rc == DSC_OK);
    assert(strcmp(buf, "1") == 0);
}

void test_read_nested_struct(void)
{
    char buf[256];
    int rc = dsc_read_var(ctx, "g_config.network.port", buf, sizeof(buf));
    assert(rc == DSC_OK);
    assert(strcmp(buf, "8080") == 0);
}
```

#### 测试组 4: 数组访问
```c
void test_read_array_element(void)
{
    char buf[256];
    int rc = dsc_read_var(ctx, "g_buffer[0]", buf, sizeof(buf));
    assert(rc == DSC_OK);
    assert(strcmp(buf, "100") == 0);
}
```

#### 测试组 5: 枚举格式化
```c
void test_read_enum(void)
{
    char buf[256];
    int rc = dsc_read_var(ctx, "g_state", buf, sizeof(buf));
    assert(rc == DSC_OK);
    /* 应包含枚举名 */
    assert(strstr(buf, "STATE_RUN") != NULL);
}
```

#### 测试组 6: Raw 内存读写
```c
void test_raw_mem_read_write(void)
{
    uint8_t write_buf[4] = { 0xDE, 0xAD, 0xBE, 0xEF };
    int rc = dsc_write_mem(ctx, addr, write_buf, 4);
    assert(rc == DSC_OK);

    uint8_t read_buf[4] = {0};
    rc = dsc_read_mem(ctx, addr, read_buf, 4);
    assert(rc == DSC_OK);
    assert(memcmp(read_buf, write_buf, 4) == 0);
}
```

### 9.4 编写 Error-Path 测试

```c
void test_read_nonexistent_var(void)
{
    char buf[256];
    int rc = dsc_read_var(ctx, "no_such_var", buf, sizeof(buf));
    assert(rc < 0);  /* 应返回错误码 */
    /* last_error 应有描述 */
    assert(strlen(dsc_last_error(ctx)) > 0);
}

void test_read_invalid_member(void)
{
    char buf[256];
    int rc = dsc_read_var(ctx, "g_config.no_such_field", buf, sizeof(buf));
    assert(rc < 0);
}

void test_read_array_out_of_bounds(void)
{
    char buf[256];
    int rc = dsc_read_var(ctx, "g_buffer[999]", buf, sizeof(buf));
    assert(rc < 0);
}

void test_open_bad_elf(void)
{
    dsc_open_params_t bad = params;
    bad.elf_path = "/nonexistent/file.elf";
    dsc_context_t *ctx = dsc_open(&bad);
    assert(ctx == NULL);
}

void test_open_null_params(void)
{
    dsc_context_t *ctx = dsc_open(NULL);
    assert(ctx == NULL);
}

void test_read_buffer_too_small(void)
{
    char buf[2];  /* 太小 */
    int rc = dsc_read_var(ctx, "g_config", buf, sizeof(buf));
    assert(rc < 0);
}
```

### 9.5 编写 Reload 测试
```c
void test_reload_preserves_transport(void)
{
    /* 修改 mock 内存中的值 */
    /* 调用 dsc_reload */
    int rc = dsc_reload(ctx);
    assert(rc == DSC_OK);
    /* 验证仍然可以读取变量 */
    char buf[256];
    rc = dsc_read_var(ctx, "g_counter", buf, sizeof(buf));
    assert(rc == DSC_OK);
}
```

### 9.6 组装测试运行器
创建一个简单的 main 函数，运行所有测试：

```c
int main(void)
{
    RUN_TEST(test_open_close_basic);
    RUN_TEST(test_close_null_safe);
    RUN_TEST(test_read_simple_int);
    /* ... */
    printf("All %d tests passed\n", test_count);
    return 0;
}
```

不使用外部测试框架——用最简单的 `assert` + 自定义 `RUN_TEST` 宏。

## Output Format
产出以下文件：
```
tests/
├── mock_transport.h    # mock transport 头文件
├── mock_transport.c    # mock transport 实现
├── test_data.c         # 测试用全局变量定义
├── test_integration.c  # 所有集成测试
└── Makefile            # 测试构建脚本
```

## Quality Checklist
- [ ] 每个 `dsc.h` 公开函数至少有一个 happy-path 测试
- [ ] 每个 `dsc.h` 公开函数至少有一个 error-path 测试
- [ ] Mock transport 正确模拟内存读写
- [ ] 测试 ELF 包含所有需要的类型（int/float/struct/enum/array）
- [ ] 所有测试相互独立（不依赖执行顺序）
- [ ] 每个测试有 setup 和 teardown（无资源泄漏）
- [ ] 每个测试函数不超过 50 行
- [ ] 测试运行后输出清晰的 PASS/FAIL 汇总
- [ ] Inventory 中 `remove` 的功能没有测试
- [ ] `make test` 可以编译并运行所有测试

## Edge Cases
- 如果没有 test ELF 文件（CI 环境），测试应能从源码自动编译生成
- 如果 mock transport 的内存大小不够，测试 setup 应报明确错误
- 如果 DWARF 解析器依赖特定 libdwarf 版本，在 Makefile 中检查

## When Unsure
- **不确定某个 API 的期望行为？** 查 `dsc.h` 的注释——它是 API 契约
- **不确定格式化输出的精确格式？** 先运行一次，用实际输出作为 expected
- **不确定 mock transport 怎么模拟地址？** 使用 0x10000 作为基地址，线性映射
- **不确定是否需要并发测试？** 不需要——dsp-connect 是单线程库
