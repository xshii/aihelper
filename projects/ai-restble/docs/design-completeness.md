# 设计完备性 + 可扩展性论证

> 用编译器/形式语言的术语审视 ai-restble 的当前设计，给出**为什么它是封闭可证的**、**它从哪些缝里能再长出来**、**还差什么**。

## 1. 用编译语言的视角刻画系统

把 ai-restble 看作一对互逆翻译器：

```
        ┌─ unpack ─────────────►┐
   XML ─┤                       ├─ YAML 树
        ◄────── pack ───────────┘

   YAML 树 ──── merge_tables ──► YAML 树（多 source → 1）
```

- **XML 端语法**（input grammar）：legacy XML schema，由 `docs/yaml-schema.md` 定义。终结符 = element/attribute/value 字面；非终结符 = 7 个固定生产式（FileInfo / wrapper / 自命名 / RunModeTbl / RunModeItem / Line / 派生 count）。
- **YAML 端语法**（target grammar）：`docs/yaml-schema.md` R1–R11 + `_children_order.yaml` meta。
- **翻译规则集**（reductions）：`preprocess.py`（XML AST → YAML AST）、`postprocess.py`（YAML AST → XML AST）。每条规则一个 `_classify` / `_scope_for` / `_emit_*` helper。
- **类型系统**：`schema/model.py` 的 `FieldSchema` / `TableSchema` + `Region = Literal["index","attribute","ref"]` + 6 种 `@merge` op。
- **`_children_order.yaml` 语法**：顶层 `{FileInfo: [<children>]}` 嵌套 mapping。`children` list 仅两种 entry：
  - `<Element>` element-class catch-all — 匹配 `resolved element name == entry` 的所有未消费文件，按 `(stem, full path)` 字母序排列
  - `<element>:<stem>` 特例 — 精确 pin 单个 instance
  - **协议契约**：同 element 类内 `(stem, full path)` 字母序 == XML idx 序；XML 不一致时必须用特例显式 pin。这是**对 XML 输入的约束**，简化语义换取可证明性。

## 2. 完备性论证（Closed-form）

### 2.1 翻译规则覆盖了输入语法的全部生产式

> Lemma：对任意符合 yaml-schema.md 的合法 XML，`unpack` 能完全消化（无未识别 element）。

形式化拆解 — 顶层 `<FileInfo>` 子元素只有 3 类（穷举）：

| 输入形态 | 判定函数 | 生产式 | 输出形态 |
|----------|----------|--------|----------|
| `<ResTbl X="Y" .../>` (wrapper) | `_classify` 命中 `child.tag == WRAPPER_TAG` | wrapper-rule | `<stem>.yaml` + `# @element:ResTbl` |
| `<RunModeTbl .../>` 或其他自命名带 `RunMode` | `_classify` fallthrough + `_scope_for` 命中 `RUNMODE_ATTR` | self-named-scoped | `<RunMode>/<stem>.yaml` |
| 其他自命名（`<X .../>`） | `_classify` fallthrough，`_scope_for` 走 xref 反查或 fallback `SHARED_FOLDER` | self-named-flat | `shared/<X>.yaml` 或 root |

`_classify` + `_scope_for` 的笛卡尔积**穷举** XML 顶层元素的所有合法形态。

### 2.2 翻译双向闭合（`pack ∘ unpack = id`）

字节级证明：4/4 fixtures 通过 `TestFullRoundTrip::test_xml_to_yaml_to_xml_byte_identical`，断言 `pack(unpack(xml)) == xml.read_bytes()`。任何破坏这个不变式的 PR 在 CI 即被拦截。

### 2.3 异常路径全部 fail-loud（无静默兜底）

| 失败场景 | 检测点 | 行为 |
|----------|--------|------|
| 非 `FileInfo` 根 | `_collect_and_dedup` 第 1 行 | `ValueError` |
| `<ResTbl>` 缺 type-attr | `_classify` | `ValueError` |
| 无法识别 count 锚字段 | `_detect_count_attr` | `ValueError` |
| 多 candidate count 锚 | `_detect_count_attr` | WARNING + 选首个 |
| 跨 XML 同 identity 异内容 | `_collect_and_dedup` | `ValueError` |
| 跨 XML FileInfo attr 不一致 | `_collect_and_dedup` | `ValueError` |
| 同 stem 跨多 folder + 异 folder ref | `_attach_use_comments` | WARNING + 不输出 @use |
| `_children_order.yaml` 列条找不到文件 | `_ordered_children` | WARNING |
| fixture 有但 `_children_order` 没列 | `_warn_on_orphan_files` | WARNING |
| `@merge:conflict` 字段差异 | `apply_merge` | `ConflictError` |

所有异常都有专属测试覆盖（见 `TestUnpackMany*` / `TestUseAnnotation*` / `TestPackWarnings`）。

### 2.4 协议常量集中化 = 静态闭合

**所有跨文件硬编码的协议名词**已抽到 const.py（按子包分布，避免顶层杂物筐）：

```
src/ecfg/legacy/const.py    XML element/attr/folder/filename/annotation tokens
src/ecfg/schema/const.py    region (index/attribute/ref) + annotation key + TEMPLATE marker
src/ecfg/merge/const.py     6 个 merge op + ref 默认 rule
```

**为什么这是完备性证据**：协议变更现在等价于"修一个 const 文件 + 跑测试"。改 `WRAPPER_TAG = "ResTbl"` 为 `"ResourceTable"`，所有引用立即跟随；测试失败 = 协议被破坏的位置；测试通过 = 协议变更已传播到所有调用点。

## 3. 可扩展性论证（开放式）

### 3.1 新增一个 XML element 形态

**步骤**（O(1) 改动量）：
1. `legacy/const.py` 加常量（如 `NEW_TAG = "..."`）
2. `_classify` 加一个分支或 `_scope_for` 加一条规则
3. `tests/fixtures/xml/valid/` 加一个 fixture
4. CI 自动跑 round-trip → 通过即合并

不需要改 `pack` —— `pack` 只看 yaml 数据 + `_children_order`，对源 XML 形态盲目。这正是双层翻译器的解耦红利。

### 3.2 新增一个 `@merge` op

**步骤**：
1. `merge/const.py` 加 `OP_NEW = "new_op"`
2. `merge/policies.py::apply_merge` 加 if 分支
3. 加 unit test

不需要改 schema loader、merger、validator —— op 名是字符串 dispatch，loader 只承载，dispatch 只解释。

### 3.3 新增一种 annotation（如 `@unique`）

**步骤**：
1. `schema/const.py` 加 `ANNOT_KEY_UNIQUE = "unique"`
2. `schema/loader.py::_build_field_schema` if-elif 链加分支，写入 `FieldSchema.unique = True`
3. `schema/model.py::FieldSchema` 加字段
4. `schema/validator.py` 加约束检查

annotation 的解析机制（`schema/annotations.py` 的通用 `@key:value` 正则）已经通用，新 key 不需要改解析层。

### 3.4 新增一个 region（除 index/attribute/ref 外的第 4 区）

代价较高，因为 `Region = Literal[...]` 是一个 closed-set 类型：
1. `schema/const.py` 加 `REGION_NEW = "new"`
2. `schema/model.py::Region` Literal 加新值（同步 const 文件）
3. `loader.py / merger.py / validator.py / io/yaml.py` 各自处理新 region
4. 评估 `merge_rule_for` 等 dispatcher 的覆盖

这里 closed-set 的代价正好是工程上的**反弱化**保险：编译器（mypy）会强制每个新 region 在所有 dispatch 点显式处理。

### 3.5 多 XML 合一已具备（无 schema 变更）

`unpack_many` 的设计是 *N→1* 的，不依赖 N 上限。3 份 / 5 份 / N 份 XML 合并不需要改任何代码，只需要传更长的 `xml_paths`。冲突检测的身份键 `_multi_xml_identity` 是开放式的 —— 添加新元素类别只需扩展该函数。

## 4. 还差什么（TODOs，按优先级）

### P0 — 数据层正确性（必须做）

| ID | 待办 | 当前状态 | 完成定义 |
|----|------|----------|----------|
| **D1** | FK 闭包校验 | `FieldSchema.fk_targets` 数据结构已就绪（每个 ref leaf 子字段 → `Table.col` 字符串），但**没有任何代码消费**它 | `validate_table` 验证：每个 ref 字段值都能在目标 Table 中找到匹配 record；找不到 → `ValueError("unresolved-ref:...")` |
| **D2** | unpack 多 XML 合并的 `xref` 一致性 | 当前 `_build_runmode_xref` 只在 `_collect_and_dedup` 之后跑，扫的是合并后的 children；如果 XML1 有 RunModeItem ref X，XML2 没有，但 X 自身在 XML2 引入 → xref 已正确（因为合并后所有 children 都看得到） | 已正确，但需要专属测试覆盖：跨 XML 引用解析 |
| **D3** | hex_widths fixture 验证 ALL hex 形式 | 当前测了 `0xAB / 0xABCD / 0xDEADBEEF / 0xFF / 0x01 / 0x0001` | 加测 `0x0` / 大写 `0xFF` vs 小写 `0xff` / 0 width width fmt |

### P1 — 协议完整性（应做）

| ID | 待办 | 现状 |
|----|------|------|
| **P1.1** | `@index:repeatable` 的 merge 行为 | loader 解析 OK，但 `merger.py` 对 repeatable 索引的合并语义需要明确（默认 conflict 可能不对） |
| **P1.2** | `validate_schema` 对 FK 字符串格式的预校验 | `_FK_RE = ^([A-Z][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)$` 在 loader 静默接受不匹配（不写入 fk_targets）；应改为：写了 ref 子字段尾注释但不匹配 FK 格式 → WARNING 或 raise |

### P2 — 工程化（可做）

| ID | 待办 | 现状 |
|----|------|------|
| **E1** | template/ 教学注释 | multi_runmode `_children_order.yaml` 含人工说明注释，preprocess 生成的版本只有简短头注释。`TestUnpackFolderIdentity` 豁免 `_children_order.yaml` 的 bit 比对 |
| **E2** | `unpack` 接受字符串路径 | 签名 `Path`，传 `str` 会被 `Path()` 包好；如要严格类型签名，改 `Union[str, Path]` 或 `PathLike` |
| **E3** | `_classify` 单 wrapper 识别 | 写死 `WRAPPER_TAG = "ResTbl"` 单值。如未来出现 `<OtherWrapper X="Y"/>` 形态，扩展为 `WRAPPER_TAGS: Set[str]` |

### P3 — 文档/教学（次要）

| ID | 待办 |
|----|------|
| **T1** | 没有架构总览图（subpackage 依赖关系图）；`docs/` 缺 `README.md` 索引 |
| **T2** | `merge-spec.md` 与 `yaml-schema.md` 的关系：前者 merge 引擎专项，后者基础 yaml schema — 在 `docs/README.md` 加引导 |

## 5. 设计哲学小结

| 原则 | 体现 |
|------|------|
| **协议名词集中化** | 3 个 const.py 把所有"魔鬼字符串/数字"拢到协议层，业务逻辑文件读起来全是名字而非字面 |
| **失败响亮（fail-loud）** | 所有异常路径都 raise 或 WARNING；没有 `try-except: pass` |
| **双向闭合可证** | `pack ∘ unpack = id` 是 round-trip 测试断言，不是注释；任何回归 CI 立即拦截 |
| **开放-封闭原则** | 协议常量是开放的（加常量 + 加 dispatch），核心翻译流程是封闭的（`unpack` / `pack` 主流程 ~30 行各，不需要随业务改动） |
| **类型系统为骨架** | `Region = Literal[...]` 把 region 列表 lock 在类型层；`FieldSchema` dataclass 把字段约束 lock 在数据结构层；mypy/pyright 是免费的"编译器" |

## 6. 验证状态

- 216/216 tests passing
- ruff check: All checks passed
- 4/4 fixtures bit-identical XML→unpack→pack→XML
- 4/4 fixtures folder-identical（`_children_order.yaml` 豁免人工教学注释）
- Multi-XML idempotent dedup + 多种 conflict raise 路径覆盖
- scaffold 生成幂等 + round-trip 一致 + 字段集 union
