# Spec 0002 — L3 离线解码器(聚合 + 组合式解码 + 外部引用)

- 状态:草案,待审 · 日期:2026-05-27
- 输入:L1/L2 插桩跑出的 `trace.jsonl`(`call` 记录含公共头/参数,`macro` 记录含原始 words)。
- 目标:把"透传码流"还原成**有意义的算子配置**。插桩(L1/L2)只 dump,不解释;解释全在这里(离线)。
- 标注:**【已定】**=用户已确认 · **【假设】**=待点头 · **【待定】**=项目数据缺口,实现前/接真实硬件前补。
- 渐进式披露:是什么→L0;三块设计→L1;决策→L2;待你补的项目数据→L3。

---

## L0 · 一句话

trace 里 `macro` 记录是**纯透传 word**,没有语义。L3 离线把它解出来,分三块:

> **聚合(L3-a)**:按执行顺序把一个算子的整套 `call`+`macro` 聚成一条 `OpRecord` →
> **组合式解码(L3-b)**:用「公共头 + 有序原子结构体 + op-kind 判别」的声明式 schema 把 word 流解成命名字段 →
> **外部引用(L3-c)**:遇到 `ref` 字段(地址)就追到另一个文件、递归解码。

schema 用 **Python 声明式**(像原 rules/,项目放 schema 目录动态加载);真实位宽/布局是**项目配置**,框架不写死。

---

## L1 · 三块设计

### L3-a 聚合阅读器(纯函数)

- 线性扫描 `trace.jsonl`:遇 `call` 开一个 op 桶;后续 `macro` 归入当前桶,直到下一个 `call`。
  (Q3 已确认 macro 紧跟其 intrinsic 的执行顺序可靠 → bracketing 成立。)
- 产出:

```python
@dataclass
class OpRecord:
    op: str                  # intrinsic 名(来自 call)
    fn: str | None           # 父函数
    common: dict             # commopheader 已解字段(opid/aopid/...)
    macros: list[MacroHit]   # 该 op 的整套硬件宏(每条带原始 words)
```

- 纯函数、零 IO(传入已读的记录序列),易测。
- `common` 与解码输出是 **schema 驱动的动态字段树**,用 `dict` 表示 —— 这是对「结构化数据不用裸 dict」的**有意例外**(键集随项目 schema 变,无法静态建模)。`OpRecord` 本身仍是 `@dataclass`。

### L3-b 组合式解码器

**schema 原语(Python 声明式)**:

```python
# 项目 schema 目录,动态加载(框架只定义这些类型)
W = 32  # 字长,项目配置

CTRL = Atom("ctrl", [Field("opcode", U(8)), Field("mode", U(4)), Field("rsv", U(20))])
ADDR = Atom("addr_blk", [Field("base", U(16)), Field("wptr", REF(blob="weights"))])

LAYOUTS = {                                  # op-kind → 该算子的自定义配置布局
    "CONV": Layout([CTRL, ADDR]),            # 公共头之外,有序 atoms 拼装
    "POOL": Layout([CTRL]),
}
DISPATCH = Dispatch(source="common.optype")  # op-kind 来源:公共头字段(或某公共宏值)
```

- `Field(name, width, type)`:type ∈ `U(bits)` / `I(bits)`(标量)、`REF(blob=...)`(外部引用)。
  (`Enum`/符号化解码 **YAGNI,先不做**,真有字段需要再加。)
- `Atom(name, fields[])`:一个原子结构体(一个 word 上的位域,或跨多 word)。
- `Layout(atoms[])`:某算子种类 = 公共头 + **有序 Atom 序列(扁平拼装)**。Atom 嵌套(Field 装另一个 Atom)是**可延后扩展**,真有子结构再加。
- `Dispatch(source)`:从 `OpRecord.common` 的某字段(op-kind)选用哪个 `Layout`。
- **框架 vs 项目(端口与适配器,同 0001 的 rule/rules_loader 模式)**:`schema.py` 只定义
  `Field/Atom/Layout/Dispatch` *类型*;项目把 *实例* 放 schema 目录,由 loader 动态加载——框架零项目值。
- **引擎对 Field type 用 `match`** 分发(`U`/`I`/`REF`/嵌套 各一支),不用字符串标签(type 是不同 dataclass)。

**引擎**:`decode(op_record, schema) -> dict`
1. 取 `common`(L3-a 已解的公共头)。
2. 用 `DISPATCH.source` 拿 op-kind → 选 `Layout`。
3. 把该 op 的 `macros` 的 words 拉平成一个 **bit 流**,按 `Layout` 的 atoms 顺序消费 → 命名字段树。
4. 遇 `REF` 字段 → 交给 L3-c。

### L3-c 外部引用解析

- `REF(blob=...)` 字段解出一个地址(偏移)→ 调用注入的 **resolver 端口**取外部字节:

```python
class BlobResolver(Protocol):
    def fetch(self, blob: str, addr: int, length: int | None) -> bytes: ...
```

- 取回的字节用(另一套)Atom schema **递归解码**(复用 L3-b 引擎)。
- 框架不写死外部文件来源:resolver 由组合根注入(可读本地文件 / 内存 / 其他)。

---

## L2 · 决策(仅结果)

- **D1** 解释全在离线 L3(插桩只 dump);与 L1/L2 解耦,只吃 `trace.jsonl`。
- **D2** L3-a 按执行顺序 bracketing 聚合(Q3 已确认顺序可靠)。
- **D3** schema 用 **Python 声明式**,项目放 schema 目录动态加载;框架零项目值。
- **D4** 布局 = 公共头 + 有序原子结构体;原子可嵌套;op-kind 判别选 Layout。
- **D5** 外部引用 `REF` 经注入的 `BlobResolver` 取字节 → 同一引擎递归解码。
- **D6** 引擎是纯函数(IO 经 resolver 端口),便于测试。
- **D7** 校验**只在边界**:trace 是外部输入(坏记录 / 缺 op-kind / word 流不够长 / `REF` 指向未知 blob → 抛具体异常);schema 是内部配置,信任不防御。失败路径必须进测试(testing-conventions)。
- **D8** 解码输出确定性(同 trace+schema 同结果),不依赖时间/随机/遍历序。

---

## L3 · 待你补的项目数据(接真实硬件前)

- **P1** 字长 `W` / 字节序 / 位序(word 流怎么拉平成 bit 流)。
- **P2** op-kind 的确切来源:`commopheader` 的哪个字段,还是某个"公共宏"的某 word?(对应 Q5 的"公共宏指定算子种类")
- **P3** 各算子种类的**真实 Layout**(哪些 Atom、字段位宽)——这是项目 schema 内容,你按框架填。
- **P4** 外部文件:`REF` 的地址是相对谁的偏移?外部内容用哪套 Atom schema?`BlobResolver` 怎么定位文件(Q4 寄存器「PC 运行版」可能就是这层来源)。

> 公共头不在此列:L1 已把 commopheader dump 成命名字段写进 `call` 记录,L3 直接读,无需位解码。
> 框架(L3-a/b/c 引擎 + schema 原语 + resolver 端口)不依赖以上;以上是**项目 schema/配置**的内容,框架就绪后填入即可跑真实数据。

---

## 落点与分层

- 新包 `pa_debug/l3_analyzer/`(reader / schema / decoder / resolver / schema_loader)。
- import-linter 契约更新为:
  `layers = ["pa_debug.cli", "pa_debug.l1_transformer | pa_debug.l3_analyzer"]`
  —— cli 在上(唯一组合根),l1/l3 同属下层但**互相独立**(`|`,不得互 import);l3 只读 trace 文件,不碰 l1。
- 组合根(cli)注入 `BlobResolver` 具体实现;`l3_analyzer` 内只依赖 `BlobResolver` 抽象(Protocol)。
