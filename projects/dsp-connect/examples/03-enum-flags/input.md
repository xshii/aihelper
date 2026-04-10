# Example 3: 枚举和位标志

## 场景

```c
typedef enum {
    STATE_IDLE    = 0,
    STATE_RUNNING = 1,
    STATE_ERROR   = 2,
    STATE_DONE    = 3,
} state_t;

typedef enum {
    FLAG_VERBOSE = 0x01,
    FLAG_DEBUG   = 0x02,
    FLAG_TRACE   = 0x04,
    FLAG_PROFILE = 0x08,
} debug_flags_t;

state_t g_state = STATE_RUNNING;
debug_flags_t g_flags = FLAG_VERBOSE | FLAG_TRACE;  /* = 0x05 */
```

## 操作

```c
dsc_read_var(ctx, "g_state", buf, sizeof(buf));
dsc_read_var(ctx, "g_flags", buf, sizeof(buf));
```
