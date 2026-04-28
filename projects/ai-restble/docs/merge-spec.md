# ecfg Merge Specification (MVP)

本文件是 ecfg 数据 YAML（merge-spec 用例，多 team 融合）的**权威规则参考**。AI agent 或人在写 `tables/*.yaml` 时应遵循此规范。

> **作用域提醒**：本文档针对 ecfg 的"多 team 融合"用例（参见 `examples/tables/Interrupt.yaml`）；与 legacy XML 用例（`docs/yaml-schema.md`、参见 `tests/fixtures/xml/valid/multi_runmode.expected/`）是**两套并行子系统**，schema 不互通。

---

## 1. 数据模型：三区域

每条 record 有三个区，顶层是 YAML list：

```yaml
- index:           # 身份字段（composite key）
    vector: 10
  attribute:       # 自持属性
    priority: 2
  ref:             # 跨表关联
    owner:
      moduleType: uart
```

- 一个 `resource_type` 对应**一份** `tables/<BaseName>.yaml` 文件
- AI agent 工作单元 = 一份文件（"极度隔离"原则）

---

## 2. Schema 通过 `@` 注释承载

**不存在单独的 schema 文件**。所有约束和规则都写在数据 YAML 的注释里，工具按位置和前缀识别。

### 2.1 字段值后：字段级约束 / 规则

```yaml
attribute:
  priority: 2             # @range: 0-15; @merge: concat(',')
  trigger: edge           # @enum: edge, level
```

多个标记用 `;` 分隔。

### 2.2 `ref` 字段：FK 目标 + 可选 merge 规则

ref 子字段后的 `<BaseName>.<field>` 声明 FK 指向：

```yaml
ref:
  owner:
    moduleType: uart      # Module.moduleType
    moduleIndex: 0        # Module.moduleIndex
```

形式为 `<BaseName>.<field>`（不带 `@`）。

ref 条目（整个子结构）的 merge 规则写在**条目键行尾**：

```yaml
ref:
  owner_module:           # @merge: conflict
    moduleType: uart      # Module.moduleType
    moduleIndex: 0        # Module.moduleIndex
```

**注释辨识规则**（ref 区）：
- 形式严格匹配 `<Identifier>.<Identifier>` 的注释 → FK 指向
- `@` 开头的注释 → annotation（`@merge` / `@count` / ...）
- 其他一切 → freeform 人类注释，工具忽略

### 2.3 TEMPLATE 块：表级声明 + 字段清单

每份表文件首部有一个被注释掉的完整 record 示例，作为**字段清单和规则的权威源**：

```yaml
# tables/Interrupt.yaml
#
# ----- TEMPLATE BEGIN -----
# - index:
#     vector: 0                   # @range: 0-255
#   attribute:
#     handler: h                  # @merge: concat(',')
#     priority: 0                 # @merge: concat(',')
#     retry: 0                    # @merge: sum
#   ref:
#     owner_module:
#       moduleType: uart          # Module.moduleType
# ----- TEMPLATE END -----
```

**真实 record 继承 TEMPLATE 的所有声明**，不需要重复 `@range / @enum / @merge`。

#### 位置约束

- TEMPLATE 块 **必须且仅有一个**，位于文件顶部（首条真实 record 之前）
- 没有 TEMPLATE 块的表文件 = 无 schema 信息，退化为 "所有字段默认不比较"（兼容 Excel 导入产物）
- 多个 TEMPLATE 块 → schema 加载期报错

#### 解析流程（实现说明）

工具恢复 TEMPLATE 内容分两步：

1. **剥注释前缀**：TEMPLATE BEGIN / END 之间每行去掉开头的 `# `（一个 `#` 加一个空格），得到合法 YAML + 注释
2. **YAML 重解析**：用 ruamel.yaml 解析剥后内容，拿到一条 record AST + 尾随注释；从注释里抽 `@` annotation 和 FK 指向

### 2.4 注释解析规则

一条 YAML 注释（去掉前导 `#`）内允许同时包含 `@` annotation 和人类 freeform 说明。解析规则：

1. 按**顶层 `;`** 切分注释 —— 顶层 = 不在 `()` / `[]` / `{}` / `""` / `''` 嵌套里
2. 对每段（去首尾空白后）：
   - 若段以 `@<标识符>:` 开头 → **annotation**：key = 标识符，value = `:` 后内容（到段末）
   - 否则 → **freeform**，工具忽略
3. 空段跳过

**对照表**（展示注释内容，省略前导 `#`）：

| 注释 | annotations | freeform |
|---|---|---|
| `@range: 0-15` | `[(range, "0-15")]` | `[]` |
| `@range: 0-15; @merge: concat(',')` | `[(range, "0-15"), (merge, "concat(',')")]` | `[]` |
| `优先级越高越先响应; @range: 0-15` | `[(range, "0-15")]` | `["优先级越高越先响应"]` |
| `@range: 0-15; V2 起才支持` | `[(range, "0-15")]` | `["V2 起才支持"]` |
| `优先级; @range: 0-15; V2 起才支持` | `[(range, "0-15")]` | `["优先级", "V2 起才支持"]` |
| `@merge: concat(';')` | `[(merge, "concat(';')")]` | `[]` |
| `@enum: ["a;b", "c"]` | `[(enum, '["a;b", "c"]')]` | `[]` |
| `优先级（不要写 @xxx）` | `[]` | `["优先级（不要写 @xxx）"]` |
| `@foo bar`（无冒号） | `[]` | `["@foo bar"]` |
| `优先级 @range: 0-15` | `[]` | `["优先级 @range: 0-15"]` |

**关键约束**：

- annotation 必须**在段的开头**。`# 优先级 @range: 0-15`（无 `;`）整段视为 freeform，`@range` 不生效。需要 annotation 生效时用 `;` 分：`# 优先级; @range: 0-15`
- **括号/引号内的 `;` 不算分段符**：`@merge: concat(';')` 完整保留
- **未知 `@` key**（如 `@author`）：加载期警告不报错，值仍被解析但不消费

## 3. `@` 标记汇总

### 字段级（写在值后）

| 标记 | 生效区 | 含义 | 实现阶段 |
|---|---|---|---|
| `@range: min-max` | index / attribute | 数值范围约束 | Phase 1 |
| `@enum: v1, v2, ...` | index / attribute | 枚举值约束 | Phase 1 |
| `@merge: <rule>` | attribute / ref 条目键后（仅形态 A） | 融合规则，见 §4 | Phase 1 |

### ref 区：两种形态

**形态 A — 单条引用**：ref 子字段的值是 mapping（复合 key），每个子字段后写 FK 目标：

```yaml
ref:
  owner_module:           # @merge: conflict       （可选，声明本 ref 条目的合并规则）
    moduleType: uart      # Module.moduleType
    moduleIndex: 0        # Module.moduleIndex
```

子字段尾的 `<BaseName>.<field>` 不带 `@`，纯 FK 指向。

**形态 B — 聚合引用**：ref 子字段的值是标量，紧跟 `@<op>` 注释描述聚合规则：

```yaml
ref:
  coreNums: 10            # @count: Module where coreType == 0
  enableMask: 0x0111      # @bitmap: Irq.vector where enabled == True
  memTotal: 0x100000      # @sum: MemRegion.size
```

支持的聚合 op（Phase 1+ 实现）：

| op | 含义 | 空集返回 |
|---|---|---|
| `@count` | 符合条件的记录数 | `0` |
| `@sum` | 某字段求和 | `0` |
| `@list` | 字段列表 | `[]` |
| `@bitmap` | 字段值作为位索引的 bitmap | `0` |
| `@max` | 最大值 | raise |
| `@min` | 最小值 | raise |

语法：`@<op>: <BaseName>[.<field>] [where <expr>]`，筛选表达式走 `simpleeval`（Python 子集）。

---

## 4. Merge 规则（6 种）

| 规则 | 语法 | 行为 | 适用类型 |
|---|---|---|---|
| `conflict` | `@merge: conflict` | 不等即 raise | 任意 |
| `concat` | `@merge: concat(SEP)` | 用 SEP 拼成 str | 任意 |
| `sum` | `@merge: sum` | 数值相加 | int / float |
| `max` | `@merge: max` | 取最大 | 可比较 |
| `min` | `@merge: min` | 取最小 | 可比较 |
| `union` | `@merge: union` | 并集去重；scalar 自动升为单元素列表 | list / scalar |

**默认**（无 `@merge:`）：不比较差异，取首条的值。

**强烈推荐 ref 字段（形态 A）显式写 `@merge: conflict`**，避免隐性数据丢失。

#### 细节约定

- **`@merge: conflict` 在 ref 形态 A 条目上的相等判定**：比较**整个子 mapping**的所有 key/value 是否一致（不区分 index 子字段和普通子字段）
- **形态 B 聚合 ref 上不允许写 `@merge`**：聚合值每次从源数据重算，不参与 team merge；schema 加载期若发现 `@merge` 标在 `@count/@sum/...` 字段上 → 报错
- **`@merge` 写在 index 字段上**：无意义（同组 index 天然相等），加载期忽略 + 警告

---

## 5. Merge 算法

给定多个 team 的同 `resource_type` 表，融合成一份最终表：

1. **按 index 分组**：index 完全相同的 record 尝试合并
2. **组内配对融合**（左折叠，源文件字典序）：
   1. 计算差异字段集 `D`（两条 record 中值不相等的字段，含 attribute 与 ref）
   2. `D_ruled` = D 中**有 `@merge:` 声明**的字段；`D_unruled` = D \ D_ruled
   3. **Raise 若**：任何 `@merge: conflict` 字段落在 D_ruled
   4. **允许合并若**：`D_ruled` 中所有字段都有非 `conflict` 的 `@merge` 规则
   5. **D_unruled 不参与阻断判定**——无规则字段的差异永远被宽容
3. **应用规则**：
   - `D_ruled` 每字段按自身 rule 合
   - `D_unruled` 每字段 → 取首条的值（即左折叠过程中保留的那条）

### 顺序稳定化

concat / union 元素按**源文件名字典序**串联，不随机。

### Schema 加载期校验

- `@merge: sum/max/min` 要求字段是数值型（通过实际值推断）

---

## 6. 举例

### 6.1 单字段独立合并

```yaml
# - attribute:
#     description:                # @merge: concat('; ')
```

两条：`description` 不同，其他全等 → `D_ruled = {description}` → 独立 concat → 成功。

### 6.2 多字段并列 + 独立聚合

```yaml
#   attribute:
#     handler: h                  # @merge: concat(',')
#     priority: 0                 # @merge: concat(',')
#     retry: 0                    # @merge: sum
```

两条：handler/priority/retry 都不同 → 每个字段都有非 conflict 规则 → 合并成功：
- handler 并列 concat：`"h1,h2"`
- priority 并列 concat：`"2,5"`
- retry 相加：`7`

### 6.3 规则字段 + 无规则字段混合

```yaml
#   attribute:
#     handler: h                  # @merge: concat(',')
#     description:                # 无规则
```

两条：handler 和 description 都不同 → `D_ruled = {handler}`（按 concat 合并），description 取首条 → 合并成功。

### 6.4 显式拒绝

```yaml
#   attribute:
#     handler: h                  # @merge: conflict
#     priority: 0                 # @merge: concat(',')
```

两条 handler 不同 → `D_ruled` 含 conflict 字段 → **raise**。改 `handler` 为 `@merge: concat(',')` 即可放过。

---

## 7. 边界情况

### 7.1 注释/语法

- **SEP 必须是带引号的字符串**：`concat(',')` / `concat('; ')` / `concat(" | ")`；裸 `concat(;)` 是语法错误
- **`@range / @enum` 的时机**：对**每条 record 的原始值**检查；merge 后的 concat 结果（字符串）不再检查
- **缺失字段**：record 里不存在某 key 视为 null；与显式 `null` 等价，不算入差异集

### 7.2 TEMPLATE / schema

- **文件无 TEMPLATE 块**：退化为"所有字段默认不比较"（Excel 导入产物的默认状态），不报错
- **真实 record 有字段但 TEMPLATE 未声明**：schema 加载期警告（未知字段）；字段按"无 @merge" 默认行为处理（取首条）
- **真实 record 缺了 TEMPLATE 声明的字段**：视为 null（等同"缺失字段"）
- **多个 TEMPLATE 块**：schema 加载期报错

### 7.3 运行时

- **`@merge` 写在 index 上**：加载期忽略 + 警告
- **`@merge` 写在聚合 ref（形态 B）上**：schema 加载期报错
- **左折叠的稳定性**：concat / sum / max / min / union 在多 record 折叠下都结合律成立，结果与折叠顺序无关（但元素**出现顺序**按源文件字典序）

## 8. 扩展新 merge 规则

Phase 1 之后如需新规则类型（`avg`、`ring_merge`、自定义聚合等）：

1. 往 `ecfg/merge/policies.py` 注册字典加一项
2. 本文档 §4 追加一行
3. 所有表文件都能用，**不需要任何表定制 Python 代码**

这是 schema-in-data 架构的核心收益：Python 层是 generic engine，对具体表永不感知。

---

## 附录：设计决策记录

- **为什么注释承载 schema 而非单独文件**：AI agent 打开一个文件就看到数据 + 规则 + 关联，极度隔离
- **为什么默认是"不比较"而非 conflict**：允许噪声字段（描述、注释）自由差异，只对重要字段显式 `@merge: conflict`
- **为什么没有 derived 表概念**：每个 resource_type 是独立表，级联 / 触发合并不做（smartci 的 MergeTriggerRef 被砍）
