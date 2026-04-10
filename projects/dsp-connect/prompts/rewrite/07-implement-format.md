# Step 7: 实现格式化层

## Role
你是一个数据可视化工程师，擅长将二进制数据按类型信息格式化为人类可读的文本。

## Task
实现 `src/format/` 下的格式化层代码。
只实现现有代码中存在 AND Inventory 标记为 `keep` 的类型格式化器。

## Context
格式化层将原始字节 + 类型信息转换为人类可读的字符串。
例如：4 字节 `[0x01, 0x00, 0x00, 0x00]` + 类型 `int32_t` → `"1"`。

demo 使用分发器模式：`dsc_format()` 根据 `type->kind` 分发到子格式化器
（format_primitive、format_struct、format_enum、format_array）。

**DSP 特有格式：** 现有代码可能有 Q-format（定点数）格式化。
这是 DSP 开发中常见的需求，需要特别关注。

## Refer to Demo
逐一阅读以下文件：
- `src/format/format.h` — 主接口：`dsc_format(data, data_len, type, opts, out)`
- `src/format/format.c` — 分发器实现：switch on type->kind
- `src/format/format_primitive.h` / `.c` — 基本类型格式化（int/float/bool/char）
- `src/format/format_struct.h` / `.c` — 结构体格式化（递归）
- `src/format/format_enum.h` / `.c` — 枚举格式化（值→名称查找）
- `src/format/format_array.h` / `.c` — 数组格式化（逐元素）
- `src/util/strbuf.h` — 字符串缓冲区工具

重点关注：
- `dsc_format_opts_t` 的各个选项及其默认值
- `dsc_format_value()` 的递归深度控制
- `dsc_strbuf_t` 的使用方式（append-only 缓冲区）
- 递归格式化如何处理缩进

## Check Inventory
打开 Inventory JSON，定位格式化模块：
1. 确认现有代码支持哪些类型格式化器（keep/remove/uncertain）
2. **特别关注**：是否有 Q-format / 定点数格式化（DSP 特有）
3. 是否有自定义显示格式（如二进制、八进制、科学计数法）
4. 是否有类型特定的特殊格式化（如 MAC 地址、IP 地址）

## Rules
1. DO: 为 demo 的 `dsc_type_kind_t` 中每种类型实现格式化（或明确跳过）
2. DO: 使用 `dsc_strbuf_t` 做字符串拼接，不用 sprintf 到固定缓冲区
3. DO: 实现递归深度限制（`opts->max_depth`）
4. DO: 实现数组元素数量限制（`opts->array_max_elems`）
5. DO: 每个函数不超过 50 行
6. DON'T: 不要修改 `format.h` 中的接口定义
7. DON'T: 不要实现 Inventory 中 `remove` 的格式化器
8. DON'T: 不要在格式化层做内存读取——数据由调用者传入
9. NEVER: 不要忽略 `data_len` 的边界检查——读取不能超出 data 缓冲区
10. ALWAYS: 处理 NULL type 和 NULL data 的情况

## Steps

### 7.1 实现 format.c（分发器）
```c
int dsc_format_value(const void *data, size_t data_len,
                     const dsc_type_t *type, const dsc_format_opts_t *opts,
                     int depth, dsc_strbuf_t *out)
{
    if (!data || !type || !out) return DSC_ERR_INVALID_ARG;

    /* 递归深度检查 */
    if (opts && opts->max_depth > 0 && depth > opts->max_depth) {
        return dsc_strbuf_append(out, "...");
    }

    /* 解开 typedef/const/volatile */
    const dsc_type_t *real = dsc_type_resolve_typedef(type);

    switch (real->kind) {
        case DSC_TYPE_BASE:    return format_primitive(data, data_len, real, opts, out);
        case DSC_TYPE_STRUCT:  return format_struct(data, data_len, real, opts, depth, out);
        case DSC_TYPE_UNION:   return format_struct(data, data_len, real, opts, depth, out);
        case DSC_TYPE_ENUM:    return format_enum(data, data_len, real, opts, out);
        case DSC_TYPE_ARRAY:   return format_array(data, data_len, real, opts, depth, out);
        case DSC_TYPE_POINTER: return format_pointer(data, data_len, real, opts, out);
        /* ... 其他类型 */
        default:               return format_hex_fallback(data, data_len, out);
    }
}
```

### 7.2 实现 format_primitive.c
处理 `DSC_TYPE_BASE` 的各种编码：

| encoding | 格式化方式 |
|----------|----------|
| DSC_ENC_SIGNED | `%d` / `%ld` / `%lld`（根据 byte_size） |
| DSC_ENC_UNSIGNED | `%u` / `%lu` / `%llu`（或 hex：`0x%x`） |
| DSC_ENC_FLOAT | `%f` / `%g`（float 4字节, double 8字节） |
| DSC_ENC_BOOL | `"true"` / `"false"` |
| DSC_ENC_CHAR | `'c'`（可打印）或 `\xNN`（不可打印） |

支持 `opts->hex_integers` 选项控制整数显示格式。

### 7.3 实现 format_struct.c
递归格式化 struct/union 的每个 field：

```
{
  field1 = value1,
  field2 = value2
}
```

- 用 `opts->indent_width` 控制缩进
- 用 `opts->show_offsets` 可选显示 `/* +0x08 */` 偏移注释
- 用 `opts->show_type_names` 可选显示 `(int32_t)` 类型前缀
- 递归调用 `dsc_format_value(depth + 1)` 格式化每个 field 的值

### 7.4 实现 format_enum.c
将整数值映射到枚举名称：

```c
/* 在 enum 的 values 数组中查找匹配项 */
for (size_t i = 0; i < type->u.enumeration.value_count; i++) {
    if (type->u.enumeration.values[i].value == int_val) {
        return dsc_strbuf_appendf(out, "%s (%lld)",
            type->u.enumeration.values[i].name, (long long)int_val);
    }
}
/* 未找到：显示原始数值 */
return dsc_strbuf_appendf(out, "<unknown: %lld>", (long long)int_val);
```

### 7.5 实现 format_array.c
逐元素格式化：

```
[elem0, elem1, elem2, ...]
```

- 用 `opts->array_max_elems` 限制显示元素数（0 = 全部）
- 超出限制时显示 `... (N more)`
- 递归调用 `dsc_format_value` 格式化每个元素

### 7.6 DSP 特有格式（如果 Inventory 标记为 keep）
如果现有代码有 Q-format（定点数）格式化：

```c
/* Q15 格式：16 位整数表示 [-1.0, 1.0) 范围的小数
 * 转换公式：float_val = int_val / (1 << 15) */
static int format_qformat(const void *data, size_t data_len,
                           int q_bits, dsc_strbuf_t *out)
{
    int16_t raw = *(const int16_t *)data;
    double val = (double)raw / (double)(1 << q_bits);
    return dsc_strbuf_appendf(out, "%.6f (Q%d: 0x%04x)",
                               val, q_bits, (unsigned)raw & 0xFFFF);
}
```

注意：Q-format 的 Q 值可能需要从类型名或注释中推断。
如果无法确定 Q 值，显示原始整数并标注 `[Q-format: Q value unknown]`。

## Output Format
产出以下文件：
- `format.c` — 分发器 + 公共函数
- `format_primitive.c` — 基本类型
- `format_struct.c` — struct/union
- `format_enum.c` — 枚举
- `format_array.c` — 数组

## Quality Checklist
- [ ] `dsc_type_kind_t` 中每种类型都有对应的格式化分支（或 fallback）
- [ ] 递归深度限制正确工作
- [ ] 数组元素限制正确工作
- [ ] `dsc_format_opts_default()` 返回合理的默认值
- [ ] 所有 `data_len` 边界检查到位——不会越界读取
- [ ] struct 格式化时 field 偏移量正确使用
- [ ] enum 未找到匹配值时显示原始数值
- [ ] 指针格式化显示 `0x` 前缀地址
- [ ] 每个函数不超过 50 行
- [ ] Inventory 中 `remove` 的格式化器没有实现

## Edge Cases
- 如果 byte_size 为 0（void 类型），显示 `"<void>"`
- 如果 data_len < type.byte_size，显示 `"<truncated>"`，不越界读取
- 如果 struct 有 0 个 field（空结构体），显示 `"{}"`
- 如果数组有 0 个元素（flexible array），显示 `"[]"`
- 如果 float 是 NaN 或 Inf，显示 `"NaN"` 或 `"Inf"`

## When Unsure
- **不确定某种类型怎么格式化？** 使用 hex fallback：显示原始字节的十六进制
- **不确定 Q-format 的 Q 值？** 显示原始整数值，标注 `[Q-format: Q value unknown]`
- **不确定缩进风格？** 使用 2 空格缩进，大括号另起一行
- **不确定 float 精度？** 默认用 `%g`（自动选择最短表示）
