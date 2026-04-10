# Example 2: 读取嵌套结构体

## 场景

```c
typedef struct {
    uint32_t ip;        /* +0x00 */
    uint16_t port;      /* +0x04 */
    uint8_t  enabled;   /* +0x06 */
    uint8_t  _pad;      /* +0x07 */
} network_t;

typedef struct {
    uint32_t  mode;     /* +0x00 */
    network_t network;  /* +0x04 */
    int32_t   volume;   /* +0x0C */
} config_t;

config_t g_config = {
    .mode = 3,
    .network = { .ip = 0xC0A80164, .port = 8080, .enabled = 1 },
    .volume = -10,
};
```

## 操作

```c
// 读整个结构体
dsc_read_var(ctx, "g_config", buf, sizeof(buf));

// 读嵌套字段
dsc_read_var(ctx, "g_config.network.port", buf, sizeof(buf));
```
