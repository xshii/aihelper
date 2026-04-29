# Skill: yaml 目录 → ECharts-friendly graph JSON

## Role
你是 ai-restble 的 **graph builder skill** 实现者。任务是把 unpack 后的 yaml 目录
（legacy 路径或 schema engine 路径产物）转成**框架无关**的节点图 JSON，供前端
ECharts 渲染。

## Task
读一个 yaml 目录（含 `FileInfo.yaml` + N 个 `<Element>.yaml` + 可选 scope 子目录），
输出 `{nodes, edges, referenced_by, meta}` JSON。**不依赖任何前端框架**，纯数据投影。

## Context

- **权威协议**：`docs/yaml-schema.md`（yaml 结构）；`docs/design-completeness.md` §2 的 ref / fk_targets 数据结构
- **约束**：每条 record 最多 2 个 outgoing ref entry；同一 ref entry 内可有 N 个子字段 FK（复合外键，**渲染为 1 条边**）
- **legacy fixture 现状**：当前 4 个 fixture 全部**无 ref 数据**（扁平 + `@related:count`）；builder 必须支持空 edge 输出
- **schema 路径产物**：未来含 ref 的 yaml 形态见 `docs/merge-spec.md` 三区域 record；builder 同时支持

## Rules

| # | 规则 | 你必须做的 |
|---|---|---|
| G1 | **节点 = 表（yaml 文件）**，不是 record | 每份 `<Element>.yaml` 产 1 个 node；FileInfo 也产一个 node（kind=FileInfo） |
| G2 | scope 通过 `category` 字段表达 | 无 scope 目录 → category="root"；有 scope → category=`<scope_folder>` (如 `shared` / `0x00000000`) |
| G3 | **边聚合到表级** | 同 (src_table, ref_name, dst_table) 三元组合并为 1 条边；记录这条聚合边背后多少个 record→record 配对（`record_pairs` 列表） |
| G4 | **复合 FK = 单条边** | 一个 ref entry 多个子字段 FK → 1 条边；`fk_fields` 字段列出所有子字段名 |
| G5 | **`referenced_by` 反查表** | 每个目标 record 维护一份 referrer 列表，供前端编辑路径级联预警/级联写回 |
| G6 | **unresolved 标记** | 当 ref 值无法在目标表找到 record 时，边的 `unresolved=true`，**不抛异常**（D1 留给 validator） |
| G7 | **输出框架无关** | 字段命名不含 `echarts` / `cytoscape` 前缀；前端渲染层负责适配 |

## Steps

1. **扫 yaml 目录**：递归找所有 `*.yaml`（排除 `_children_order.yaml` 元数据）
2. **解析每份 yaml** → 复用 `ecfg.legacy._yaml.YAML_RT` 加载；提取：
   - 文件路径 → element name (stem) + scope folder
   - 顶层字段（attribute）+ list 子元素（records）
   - 每个 record 的 index 字段（schema 路径用 region；legacy 路径用约定首字段）
3. **建节点**：每份 yaml → 一个 node `{id, kind, scope, fields, records_preview}`
4. **建边**（仅 schema 路径有 ref 数据时）：
   - 遍历每个 record 的 ref 区子字段
   - 解析 fk_targets → (target_table, target_col)
   - 在目标表 records 中按 col=value 查找 → 找到则 unresolved=false 并入 `referenced_by`，找不到则 unresolved=true
   - 同 (src, ref_name, dst) 聚合，累加 `record_pairs`
5. **构建 referenced_by**：边的反查索引，key=`<target_table>.<target_col>=<value>`，value=referrer 列表
6. **输出 JSON**：`{nodes, edges, referenced_by, meta}` 结构

## Output Format

```json
{
  "meta": {
    "yaml_dir": "tests/fixtures/xml/valid/multi_runmode.expected",
    "categories": ["0x10000000", "0x20000000", "shared"],
    "node_count": 12,
    "edge_count": 0
  },
  "nodes": [
    {
      "id": "shared/DmaCfgTbl",
      "kind": "Table",
      "scope": "shared",
      "category": "shared",
      "element": "ResTbl",
      "wrapper_type": "DmaCfgTbl",
      "fields": [
        {"name": "channelId", "region": "index"},
        {"name": "srcType", "region": "attribute"},
        {"name": "dstType", "region": "attribute"}
      ],
      "records_preview": 4,
      "records": [
        {"index": {"channelId": "0x10"}, "attribute": {"srcType": "ddr"}, "ref": {}}
      ]
    }
  ],
  "edges": [
    {
      "id": "e1",
      "from": "RunModeItem",
      "to": "DmaCfgTbl",
      "ref_name": "dma",
      "fk_fields": ["channelId"],
      "unresolved": false,
      "record_pairs": [
        {"src_index": "id=cpu0", "dst_index": "channelId=0x10"}
      ]
    }
  ],
  "referenced_by": {
    "DmaCfgTbl.channelId=0x10": [
      {"src_table": "RunModeItem", "src_index": "id=cpu0", "ref_name": "dma", "edge_id": "e1"}
    ]
  }
}
```

**字段定义：**

- `meta.categories`：scope 的有序去重列表，前端按此着色
- `node.kind`：`Table` / `FileInfo` / `RunModeTbl`（自命名带 children）
- `node.element`：原 XML element name（如 `ResTbl`），用于前端 badge
- `node.wrapper_type`：仅 wrapper 节点有值（`<ResTbl X="DmaCfgTbl">` 的 X）
- `node.fields[].region`：legacy 路径全部 `attribute`；schema 路径区分 index/attribute/ref
- `node.records_preview`：record 数量（用于节点大小/标签）
- `node.records`：完整 record 列表（前端按需展开详情面板）
- `edge.fk_fields`：复合 FK 的所有子字段名，长度 1 即简单 FK
- `edge.record_pairs`：聚合边背后的具体 record 配对，前端 click-edge 弹 popover 用
- `referenced_by` key 格式：`<table>.<col>=<value>`，前端编辑级联用

## Examples

### Example 1：legacy fixture（无 ref，仅节点）

输入：`tests/fixtures/xml/valid/multi_runmode.expected/`（multi_runmode 含三 scope：
`shared/`、`0x10000000/`、`0x20000000/`，各 4 份 yaml，合计 12 节点）

输出关键片段：
```json
{
  "meta": {"categories": ["0x10000000", "0x20000000", "shared"],
           "node_count": 12, "edge_count": 0},
  "nodes": [
    {"id": "shared/DmaCfgTbl", "kind": "Table", "scope": "shared", "category": "shared",
     "element": "ResTbl", "wrapper_type": "DmaCfgTbl",
     "fields": [...], "records_preview": 1},
    {"id": "0x10000000/RunModeTbl", "kind": "Table", "scope": "0x10000000",
     "category": "0x10000000", "element": "<self>",
     "fields": [...], "records_preview": 3}
  ],
  "edges": [],
  "referenced_by": {}
}
```

### Example 2：schema 路径含 ref（未来形态）

输入 yaml 片段：
```yaml
# Module.yaml （schema 路径）
- index:
    moduleType: cpu
    moduleIndex: 0
  ref:
    dma:
      channelId: 0x10        # DmaCfgTbl.channelId
```

输出边：
```json
{
  "id": "e1",
  "from": "Module", "to": "DmaCfgTbl",
  "ref_name": "dma",
  "fk_fields": ["channelId"],
  "unresolved": false,
  "record_pairs": [{"src_index": "moduleType=cpu,moduleIndex=0", "dst_index": "channelId=0x10"}]
}
```

### Example 3：复合 FK（一个 ref 多子字段）

输入：
```yaml
# Item.yaml
- index: {id: i1}
  ref:
    module:
      moduleType: cpu     # Module.moduleType
      moduleIndex: 0      # Module.moduleIndex
```

输出边（**1 条**，不是 2 条）：
```json
{
  "id": "e2",
  "from": "Item", "to": "Module",
  "ref_name": "module",
  "fk_fields": ["moduleType", "moduleIndex"],
  "unresolved": false,
  "record_pairs": [{"src_index": "id=i1", "dst_index": "moduleType=cpu,moduleIndex=0"}]
}
```

### Example 4：unresolved（D1 路径）

输入 record `module: {moduleType: dsp, moduleIndex: 99}`，但 `Module.yaml` 里没有这条 record。

输出边：
```json
{
  "id": "e3",
  "from": "Item", "to": "Module",
  "ref_name": "module", "fk_fields": ["moduleType", "moduleIndex"],
  "unresolved": true,
  "record_pairs": []
}
```

## Quality Checklist

- [ ] 节点 id 全局唯一（同 stem 不同 scope 也唯一，用 `<scope>/<stem>` 兜底冲突）
- [ ] `meta.categories` 有序去重，与 nodes 引用一致
- [ ] 边按 (src, ref_name, dst) 三元组聚合，不重复
- [ ] 复合 FK 输出 **1 条**边，`fk_fields` 列出全部子字段
- [ ] `referenced_by` 覆盖所有 unresolved=false 的边对应 record
- [ ] 空 ref 输入 → `edges=[]`、`referenced_by={}`，不报错
- [ ] 同一 yaml 目录多次调用 → 字节级一致（dict key 顺序按字段名 / category 顺序按出现序）
- [ ] node.records 字段保留完整 record 数据（详情面板用）
- [ ] node.fields 有序（按 yaml 出现序），不丢字段

## Edge Cases

| 情况 | 处理 |
|---|---|
| 单文件（minimal fixture，无 scope）| `category="root"`，`meta.categories=["root"]` |
| 多 scope（multi_runmode）| 多个 category，前端按 category 着色 |
| ref 值为 list（@index:repeatable）| 每个 list 元素查一次 referenced_by |
| ref 字段值为 None | 视为未配置，跳过（**不**计 unresolved） |
| 目标表整个不存在 | 边 unresolved=true，`record_pairs=[]`，不抛异常 |
| 自引用（A 表内 record 引用 A 表自身另一 record） | 正常输出边，`from==to` |
| 跨 scope ref（shared → 0x00000000）| 正常输出，不做 scope 检查；validator 路径校验 scope 合法性 |

## 解决冲突的兜底原则

- **builder 是 yaml 的纯投影**：不做约束校验、不做格式转换、不引入新协议字段
- **fail-soft**：unresolved 标记 + 空 list，不 raise；raise 留给 validator 路径
- **框架无关**：JSON 字段命名不出现 echarts/cytoscape；前端层做适配
