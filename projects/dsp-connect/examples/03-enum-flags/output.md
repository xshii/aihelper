# Expected Output

## 普通枚举 `g_state`

```
STATE_RUNNING (1)
```

## 位标志枚举 `g_flags`

```
FLAG_VERBOSE | FLAG_TRACE (0x05)
```

---

**Why this output:**
- 普通枚举：精确匹配值 → 显示枚举名 + 数值
- 位标志枚举：自动检测到所有非零值都是 2 的幂 → 按位拆解，用 `|` 连接
- 如果值无法匹配任何枚举项，回退到纯数值: `5 (0x05) /* unknown enumerator */`
