/*
 * svc_compare.c — 桩 CPU 侧机制 B 比数 svc（详见 06b § 1.6.4 / § 4.6）.
 *
 * 本文件实现 mem_drv_pull_compare_batch / mem_drv_clear_compare_buf 两个语义化函数。
 * 对外 svc 名：svc_compare_pull_batch / svc_compare_clear（在 mechanism_ops_t 表中绑定）。
 *
 * 风格：参考 ai-restble 项目；常量集中、无魔法字、所有外部依赖通过 extern 声明。
 */

#include <stdint.h>
#include <string.h>

/* ─── 与 Autotest 端 dtypes.CompareEntry 等价 ─── */
typedef struct __attribute__((packed)) {
    uint16_t tid;
    uint16_t cnt;
    uint32_t length;
    uint32_t addr;          /* 32 位 DUT 指针 */
} compare_entry_t;

#define COMPARE_BUF_CAPACITY    200u
#define COMPARE_BATCH_MAX       COMPARE_BUF_CAPACITY

/* SoftDebug L6B SDK — 由其它文件提供 */
extern int  l6b_softdebug_read (uint32_t addr, uint32_t n, void *out);
extern int  l6b_softdebug_write(uint32_t addr, uint32_t n, const void *in);

/* 链接 map 中加载的 DUT 符号地址（image_activate 后由 svc_image 重载）*/
extern uint32_t g_dut_sym_debugCnt;     /* 对应 DUT 的 &g_debugCnt   */
extern uint32_t g_dut_sym_compAddr;     /* 对应 DUT 的 &g_compAddr[0]*/

/* 错误码段（与 errors.yaml 对齐）*/
#define ERR_OK                          0x0000
#define ERR_COMM_TIMEOUT                0x2001
#define ERR_DATA_INTEGRITY              0x4001
#define ERR_COMPARE_BUF_OVERFLOW        0x4002

/*
 * 拉一批比数描述符 + 数据。
 *   out_entries[0..N-1] = 描述符（按 1-based 1..N 顺序填入数组 0..N-1）
 *   out_data_buf[i] = 第 i 条对应的数据（连续平铺，由调用方按 length 切片）
 *
 * 返回：
 *    >= 0  实际项数 N
 *    < 0   错误码（取负）
 */
int svc_compare_pull_batch(compare_entry_t *out_entries,
                           uint8_t         *out_data_buf,
                           uint32_t         out_data_buf_size,
                           uint32_t        *out_data_total)
{
    uint32_t n = 0u;
    int rc;

    rc = l6b_softdebug_read(g_dut_sym_debugCnt, sizeof(uint32_t), &n);
    if (rc != 0) { return -ERR_COMM_TIMEOUT; }
    if (n == 0u) { *out_data_total = 0u; return 0; }
    if (n > COMPARE_BUF_CAPACITY) { return -ERR_COMPARE_BUF_OVERFLOW; }

    /* 一次性读全部描述符 — 减少 SoftDebug 往返次数 */
    rc = l6b_softdebug_read(g_dut_sym_compAddr,
                            n * sizeof(compare_entry_t),
                            out_entries);
    if (rc != 0) { return -ERR_COMM_TIMEOUT; }

    /* 逐条按 entry.addr 拉数据 */
    uint32_t cursor = 0u;
    for (uint32_t i = 0u; i < n; ++i) {
        if (cursor + out_entries[i].length > out_data_buf_size) {
            return -ERR_DATA_INTEGRITY;     /* 缓冲不够 */
        }
        rc = l6b_softdebug_read(out_entries[i].addr,
                                out_entries[i].length,
                                &out_data_buf[cursor]);
        if (rc != 0) { return -ERR_COMM_TIMEOUT; }
        cursor += out_entries[i].length;
    }
    *out_data_total = cursor;
    return (int)n;
}

/*
 * 整体清零 g_debugCnt（消费协议）。
 */
int svc_compare_clear(void)
{
    uint32_t zero = 0u;
    int rc = l6b_softdebug_write(g_dut_sym_debugCnt, sizeof(uint32_t), &zero);
    return (rc == 0) ? ERR_OK : -ERR_COMM_TIMEOUT;
}
