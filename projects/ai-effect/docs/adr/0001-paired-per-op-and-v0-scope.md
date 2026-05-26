# ADR 0001 — paired per-op 对比模型 + V0 范围收敛

- 状态:已采纳
- 日期:2026-05-26
- 背景:架构初稿评审后,三项承重决策(A/B/C)被采纳。

## A. 对比模型:两份独立 trace → paired per-op(逐算子配对)

**初稿**:跑硬件出一份 trace,独立跑 reference 出另一份 trace,按 op_id 对齐两份。

**问题**:reference 端到端独立跑时,第 N 个 ref 算子的输入是 ref 自己算的。两条链一旦
在前面分叉,后面全错,无法判断某算子"输入一致但输出错"(FR-4.4 的 A/B 分类做不干净)。

**决策**:硬件跑一遍 `DUMP_AND_RUN`,dump 每个算子的**输入 + 输出**;离线把每个算子的
**硬件真实输入**喂给 reference,比 `ref(硬件输入)` 与 `硬件输出`。每个算子独立成案。

**后果**:
- V0 核心路径**不需要在设备上跑 reference**,也不需要第二次 on-device run。
- Reference 从 L2(运行时 C 库)移到 **L3(离线 Python / NumPy)**。
- TraceAligner 不再需要跨两次 run 对齐 → 数据相关控制流的对齐风险大幅降低。

## B. V0 范围:只做 `DUMP_AND_RUN`,SKIP 类模式推到 V1

**问题**:`REPLACE_WITH_REF` / `DUMP_AND_SKIP` 需要"把原宏调用包进 `if` 跳过"——这是
语句改写,初稿的纯插入 Edit 模型(InsertBefore/After)表达不了;且需要 host→device 写回
路径(dump 的逆向,同样硬件相关)。

**决策**:V0 只实现 `DUMP_AND_RUN`。SKIP 类模式 + bisection(UC-2)与语句包裹一起放 V1。
配合决策 A,V0 对比本就不需要它们。`HASH_ONLY` 定位收窄为"两次硬件 run 间的廉价回归烟测",
不喂给浮点 Differ(hash 只判 bit-exact)。

## C. 免适配的边界:每种宏配声明式参数语义描述符

**问题**:硬件宏多为"裸地址 + 寄存器值",C 类型系统里 `float*` 不携带长度。"看类型自动推
shape"在宏层面推不出 size,也就 dump 不出有意义的 tensor。

**决策**:零适配能自动**插 hook**;但要 dump 出 tensor 语义(shape/dtype/字节数),每种宏
需一份**声明式描述符**(`Arg(role=..., shape_from=..., dtype=...)`),写在该宏的规则里。
文档明确写实这一边界,不给"类型能自动推出 shape"的幻觉。

## 影响的需求/章节
- 影响 FR-2(V0 模式集合)、FR-3(reference 归属层)、FR-4.1/4.4(对齐与分类机制)
- 对应 ARCHITECTURE §3(变更说明)、§6.2/§6.3(层职责)、§7.3(对比流程)
