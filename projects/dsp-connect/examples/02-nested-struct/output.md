# Expected Output

## 读整个结构体 `g_config`

```
{
  .mode = 3 (0x00000003),          /* +0x00 uint32_t */
  .network = {                     /* +0x04 network_t */
    .ip = 3232235876 (0xC0A80164), /* +0x04 uint32_t */
    .port = 8080 (0x1F90),         /* +0x08 uint16_t */
    .enabled = 1 (0x01),           /* +0x0A uint8_t */
  },
  .volume = -10 (0xFFFFFFF6),      /* +0x0C int32_t */
}
```

## 读嵌套字段 `g_config.network.port`

```
8080 (0x1F90)
```

---

**Why this output:**
- 结构体用大括号包裹，每个字段一行
- 缩进 2 空格表示嵌套层级
- 注释显示字段偏移和类型名（`show_offsets` 默认开启时）
- 嵌套结构体递归展开
- 单独读取嵌套字段时，只返回那个字段的值
