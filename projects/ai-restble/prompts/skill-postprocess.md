# Skill: YAML → XML 后处理

## Role
你是 ai-restble 的**后处理 skill** 实现者。任务是把 yaml 文件树合成回字节级稳定的 legacy XML。

## Task
读取一个目录树（含 element data yaml + `template/_children_order.yaml` 顺序 meta），输出一个 XML 文件，要求**字节级跟原始 XML 一致**（允许空白/空行差异）。

## Context
- **权威协议**：`docs/yaml-schema.md`（必读）
- **顶层元素顺序**：完全由 `template/_children_order.yaml` 决定（含 `<element>:<stem>` 特例覆盖默认字母序）
- **元素属性 emit 顺序**：按**数据 yaml 自身的 mapping insertion order**（无元素 template 概念）
- **派生字段在 emit 时算出**（`@related:count(...)`）
- **参考样例**：见 `tests/fixtures/xml/valid/*.expected/` 与对应 `.xml`

## Rules（编号同 yaml-schema.md）

| # | 规则 | 你必须做的 |
|---|---|---|
| R4 | 读首行 `# @element:<X>` | 决定物理 XML element 名（`<self>` → 文件 stem 去 variant；其他 → X 字面）。**`FileInfo.yaml` 例外**：文档根，元素名固定 `FileInfo`，无 @element 头 |
| R5 | wrapper 形态 → type-attr 推导 | name = stem 去 variant；value = stem 全名 |
| R6 | 顶层 mapping → XML attributes | 按 template 顺序输出 |
| R7 | `# @related:count(<X>)` 字段 → emit 拆分 | 该字段 emit 为 scalar attribute（值 = `len(list)`），list items 平级挂父元素下 |
| R8 | list item mapping → child element | element 名取自 R7 的 `<X>` 锚定 |
| R9 | ref value 永远 = 文件 stem | 直接写出 |
| R10 | `# @use:<path>` → 物理路径 | 按显式路径找文件；无标记 → 同目录默认 |
| R11 | `@related:T.c` 不带 variant → 同行 RunMode 锁 instance | 解析时绑定 |

## Steps

```mermaid
flowchart TD
  A[扫描目录] --> B[加载 template/_children_order.yaml + 所有 element yaml]
  B --> C[FileInfo.yaml 作为根]
  C --> D{遍历 _children_order entry}
  D --> D1{含冒号?}
  D1 -->|yes :| D2["特例：精确匹配 element:stem 文件"]
  D1 -->|no| D3["element-class catch-all：匹配 element_name == entry"]
  D2 & D3 --> E[读首行 @element:<X>]
  E --> F{X = <self>?}
  F -->|yes| G[element name = stem 去 variant]
  F -->|no| H[element name = X<br/>type-attr 由 stem 推导]
  G & H --> J[按 yaml 自身字段 insertion order 输出 attribute]
  J --> K{字段尾有 @related:count?}
  K -->|yes| L[count = len(list)<br/>list items 平级 emit 为 children]
  K -->|no| M[skip]
  L & M --> N[append 到 FileInfo 子元素]
  N --> D
  D --> O[FileInfo 包成 XML 根]
  O --> P[字节级稳定输出]
```

具体执行：

1. **扫描目录**：找出所有 element yaml（排除 FileInfo / `template/` / 下划线 meta）。
2. **加载 `template/_children_order.yaml`** —— element-class entries + `<element>:<stem>` 特例 list。
3. **拼装 XML**：
   a. **FileInfo 是文档根** —— attributes 来自 `(shared/)?FileInfo.yaml`（首行 `# @element:FileInfo`，与其他 data yaml 统一）。
   b. **逐 entry 展开**：按 list 顺序，每条 entry **只有两种形式**：
      - 不含 `:` → **`<Element>` element-class catch-all**：匹配 `resolved element name == entry` 的所有未消费文件，按 `(stem, full path)` 字母序排列。
      - 含 `:` → **`<element>:<stem>` 特例**：精确匹配 (resolved element name + 完整 stem)，pin 单个 instance 到此位置。
      
      匹配按 list 顺序贪心，每文件最多匹配一次（特例先消费，catch-all 后兜底）。**协议契约**：同 element 类内 `(stem, full path)` 字母序 == XML idx 序——XML 不一致时必须用特例显式 pin。**文件夹位置通过 path 进入 tiebreak**，不单独优先。
4. **每个文件 emit XML**：
   - 读首行 `@element:<X>` 决定 element name（含 FileInfo）
   - 按**数据 yaml 自身**字段 insertion order 输出 attributes
   - 派生字段（`@related:count(C)`）—— scalar attribute 值 = `len(list)`；list items 作为 sibling children 平级挂父元素下（**不**嵌套）
   - list item mapping 中的每个 key-value → child element 的一个 attribute
5. **字节级稳定**：
   - hex 数值保留原宽度（`0xAB` 不能输出 `0xab` 或 `0x000000AB`），ruamel rt 模式 `HexInt._width` / `HexCapsInt` 自动保
   - 空属性输出 `attr=""`
   - 无 children 自闭合：`<X .../>`；有 children 显式结束标签

## Output Format

单个 `.xml` 文件，UTF-8，含 `<?xml version="1.0" encoding="UTF-8"?>` 头，根元素 `<FileInfo>`。

## Examples

### Example 1：minimal

**Input** 目录：
```
minimal.expected/
├── FileInfo.yaml          (# @element:<self>, 6 attrs)
├── RatVersion.yaml        (# @element:ResTbl, 1 Line)
└── FooTbl.yaml            (# @element:ResTbl, 1 Line)
```

**Output** `minimal.xml`：
```xml
<?xml version="1.0" encoding="UTF-8"?>
<FileInfo FileName="min.xlsx" Date="2026/04" XmlConvToolsVersion="V0.01" RatType="" Version="1.00" RevisionHistory="">
    <ResTbl RatVersion="RatVersion" LineNum="1">
        <Line VVersion="100" RVersion="22" CVersion="10"/>
    </ResTbl>
    <ResTbl FooTbl="FooTbl" LineNum="1">
        <Line Id="0" Name="alpha"/>
    </ResTbl>
</FileInfo>
```

### Example 2：empty wrapper

`FooTbl.yaml`：
```yaml
# @element:ResTbl
LineNum: # @related:count(Line)
```
（list 为空 / null）

emit：`<ResTbl FooTbl="FooTbl" LineNum="0"/>`（自闭合，LineNum=0，无 child）

### Example 3：派生字段拆分（最重要的反直觉点）

`0x10000000/RunModeTbl.yaml`：
```yaml
# @element:<self>
RunModeDesc: "LowPower"
RunMode: 0x10000000
ResAllocMode: 0
ResTblNum: # @related:count(RunModeItem)
- ClkCfgTbl: "ClkCfgTbl"
- DmaCfgTbl: "DmaCfgTbl"
- CoreDeployTbl: "CoreDeployTbl"
```

emit：
```xml
<RunModeTbl RunModeDesc="LowPower" RunMode="0x10000000" ResAllocMode="0" ResTblNum="3">
    <RunModeItem ClkCfgTbl="ClkCfgTbl"/>
    <RunModeItem DmaCfgTbl="DmaCfgTbl"/>
    <RunModeItem CoreDeployTbl="CoreDeployTbl"/>
</RunModeTbl>
```

⚠️ `ResTblNum` 是 RunModeTbl 的 **scalar attribute**（值=3），RunModeItem 子元素 **平级挂在 RunModeTbl 下**，不是嵌套在 `<ResTblNum>` 里。

## Quality Checklist

- [ ] 输出 XML 与原始 XML **字节级一致**（`diff -w` 验证，允空白差）
- [ ] 同一 fixture 多次 pack 输出 byte-for-byte 完全一致（幂等性）
- [ ] 所有派生字段（LineNum/ResTblNum）数值 = `len(children)`
- [ ] hex 数值宽度 + 大小写都保留（`0xAB` ≠ `0xab` ≠ `0x000000AB`）
- [ ] 派生字段下的 list items **平级 emit** 为 sibling children，不嵌套到 `<count_field>...` 里
- [ ] FileInfo 是文档根，其他所有 yaml 文件作为它的 children
- [ ] 所有 ref（`@use` 显式 + 默认同目录）都成功解析到现存文件
- [ ] `template/_children_order.yaml` 缺失或非 yaml-list-of-strings → 报错，不猜
- [ ] `_children_order` 列了某 entry 但 fixture 找不到匹配 → WARNING（不丢弃静默）
- [ ] fixture 有 yaml 但不在 `_children_order` 任何 entry 下 → WARNING（不丢弃静默）

## Edge Cases

| 情况 | 处理 |
|---|---|
| yaml 文件首行 = `# @element:<self>` | element name = file stem 去 `_<variant>` 后缀 |
| FileInfo.yaml 含 `# @element:FileInfo` 头 | 与其他 data yaml 统一处理 |
| yaml 主体仅首行（空 element） | emit 自闭合 element，无 attribute 无 children |
| list 为 null（`LineNum: # @related:count(Line)` 后无 `-` items） | 派生值 = 0，emit 自闭合 element |
| 同 stem 同 element 在不同 scope folder 都存在 | **正常**——多 RunMode 数据；按 `_children_order` 顺序逐个 emit |
| 引用解析不到目标文件 | 报错 `unresolved-ref:<value>`，不静默 |
| `0xCAFE` / `0x0001` 等 hex literal | ruamel rt 模式天然保留宽度+大小写，直接 emit 不转 int |

## 解决冲突的兜底原则

- **字节级一致优先**：宁可 emit 失败也不输出"看似合法但字节有差"的 XML
- **`_children_order.yaml` 是顶层顺序的唯一仲裁者**：不依赖文件夹位置启发（无 shared/ 优先）
- **数据 yaml 自身 insertion order 是元素属性顺序的唯一仲裁者**：无元素 template 干预
- **不静默兜底**：宁报错不猜测；orphan 文件 / 不匹配的 entry 都 WARNING
- **派生字段永远算，不读 source**：即使 yaml 误填了 `LineNum: 99`，也要 ignore，按 `len(children)` 算（fail-loud：用户的源数据被忽略时至少在日志可见）
