/* PURPOSE: 编译此文件生成测试用 ELF fixture
 * 编译命令: gcc -g -O0 -o types_fixture.elf types_fixture.c
 * 包含所有需要测试的 DWARF 类型 */

#include <stdint.h>
#include <stdbool.h>

/* --- base types --- */
int32_t g_signed32 = -42;
uint8_t g_byte = 0xAB;
float g_float = 3.14f;
bool g_flag = true;

/* --- enum --- */
typedef enum {
    STATE_IDLE = 0,
    STATE_RUNNING = 1,
    STATE_ERROR = 2,
} state_t;
state_t g_state = STATE_RUNNING;

/* --- enum flags (OR'd) --- */
typedef enum {
    FLAG_VERBOSE = 0x01,
    FLAG_DEBUG   = 0x02,
    FLAG_TRACE   = 0x04,
} debug_flags_t;
debug_flags_t g_flags = FLAG_VERBOSE | FLAG_TRACE;

/* --- struct --- */
typedef struct {
    uint32_t ip;
    uint16_t port;
    uint8_t  enabled;
} network_t;

/* --- nested struct --- */
typedef struct {
    uint32_t  mode;
    network_t network;
    int32_t   volume;
} config_t;
config_t g_config = {
    .mode = 3,
    .network = { .ip = 0xC0A80164, .port = 8080, .enabled = 1 },
    .volume = -10,
};

/* --- union --- */
typedef union {
    uint32_t u32;
    float    f32;
    uint8_t  bytes[4];
} value_u;
value_u g_value = { .u32 = 0xDEADBEEF };

/* --- pointer --- */
config_t *g_config_ptr = &g_config;

/* --- typedef chain --- */
typedef uint32_t counter_t;
typedef counter_t my_counter_t;
my_counter_t g_counter = 100;

/* --- const --- */
const uint32_t g_magic = 0xCAFEBABE;

/* --- volatile --- */
volatile uint32_t g_hw_reg = 0;

/* --- array --- */
int16_t g_buffer[8] = {10, 20, 30, 40, 50, 60, 70, 80};

/* --- bitfield --- */
typedef struct {
    uint32_t a : 4;
    uint32_t b : 12;
    uint32_t c : 16;
} bitfield_t;
bitfield_t g_bits = { .a = 0xF, .b = 0x123, .c = 0xABCD };

/* keep linker happy */
int main(void) { return 0; }
