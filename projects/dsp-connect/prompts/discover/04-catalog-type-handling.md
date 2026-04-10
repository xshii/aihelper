# Step 4: 盘点类型解析和格式化

## Role
你是一个类型系统分析专家，擅长理解 DWARF 类型如何被解释和显示。

## Task
找到现有代码中**所有类型解析和数据格式化功能**，这是从"裸字节"到"可读输出"的关键环节。

## Steps

1. **找类型处理代码**
   搜索关键词：
   ```
   struct, union, enum, typedef, pointer, array, bitfield
   base_type, encoding, signed, unsigned, float
   format, display, print, dump, to_string, stringify
   sizeof, offset, alignment, padding
   endian, swap, byte_order, big_endian, little_endian
   Q_format, fixed_point, fractional
   ```

2. **记录支持的类型**
   检查代码是否处理以下每种类型，标注处理方式：

   | 类型 | 是否支持 | 处理方式 | 文件:行 |
   |------|---------|---------|---------|
   | int8/16/32/64 有符号 | | | |
   | uint8/16/32/64 无符号 | | | |
   | float32/64 | | | |
   | bool | | | |
   | char / string | | | |
   | 指针 | | | |
   | struct（含嵌套） | | | |
   | union | | | |
   | enum | | | |
   | enum flags (OR'd) | | | |
   | 数组（1D/2D） | | | |
   | typedef 链 | | | |
   | const / volatile | | | |
   | 位域 (bitfield) | | | |
   | Q 格式定点数 | | | |

3. **找格式化输出逻辑**
   - 整数如何显示（十进制？十六进制？两者都有？）
   - 结构体如何缩进显示
   - 数组截断策略
   - 枚举值→名称的映射方式

4. **识别多余的类型处理**
   - 从未在实际 ELF 中出现的类型处理代码
   - 过度复杂的格式化（如 ASCII art 表格）
   - 仅用于调试格式化代码本身的 debug 输出

## Output Format

```markdown
## 类型处理清单

### 支持的类型矩阵
[上面的表格，填完]

### 格式化策略
- 整数: [hex / dec / both]
- 浮点: [精度、特殊值处理]
- 结构体: [缩进方式、字段偏移显示]
- 数组: [截断阈值、hex dump 模式]
- 枚举: [值→名映射方式]

### 多余的类型处理
| # | 功能 | 文件 | 删除理由 |
|---|------|------|---------|

### 缺失但可能需要的类型处理
| # | 类型 | 为什么可能需要 |
|---|------|---------------|
```

## Rules
1. DO: 对每种类型明确标注"支持/不支持/部分支持"
2. DO: 找出格式化代码中的特殊逻辑（Q 格式等 DSP 特有的）
3. DON'T: 不要只记录"支持 struct"——要具体到嵌套层级、匿名 struct 等
4. NEVER: 不要跳过 bitfield——这是嵌入式中的高频类型
