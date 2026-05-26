# ai-effect — 算子调试与对照工具 (pa-debug)

> 自研 AI 加速器上,模型由 C intrinsic 编写、经自研编译器跑在硬件上。推理结果错了之后,
> 中间各算子输出无法对照、无法定位。本工具**不改自研编译器**,用源到源插桩 + 离线对照,
> 自动定位**第一个发散的算子**。

## 它解决什么

- **比对盲区** → 每个算子的输入/输出自动 dump 成结构化 trace
- **定位困难** → 离线把"硬件真实输入"喂给 host reference,逐算子比对,报告首个发散点
- **无 reference** → host 侧 NumPy 等价实现作为 golden
- **零侵入** → 算子开发者不改源码,编译开关启停,不启用时零开销

## 架构(四层,单向依赖)

```
L4  Orchestrator   CLI / pipeline           pa-debug instrument|build|run|diff|full
L3  Offline Analyzer (Python, 纯离线)        TraceReader / Differ / DivergenceLocator / Reference / Reporter
L2  Runtime Hook Lib (C, 被链接)             HookDispatcher / DmaExporter / TraceWriter   ← V0 只 dump
L1  Compile-time Transformer (Python)        libclang 解析 → 宏/算子识别 → 源码层插 hook 调用
```

依赖方向:`L4 → L3 → L2(运行时产物) / L1(编译时)`。L1↔L2 唯一耦合点是 hook 函数 ABI。

**核心对比模型(paired per-op)**:硬件跑一遍,`DUMP_AND_RUN` dump 每个算子的输入+输出;
离线把每个算子的**硬件真实输入**喂给 reference,比对"理应输出 vs 硬件真实输出"。
每个算子独立成案 → 干净区分"本算子 bug" 与 "上游传染"。**不需要在设备上跑 reference。**

## 文档

- [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) — 需求(FR / NFR / 约束 / 场景 / 成功标准)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 架构设计(已纳入评审修订)
- [docs/adr/0001-paired-per-op-and-v0-scope.md](docs/adr/0001-paired-per-op-and-v0-scope.md) — 关键决策记录

## 状态

`experimental` · V0 PoC 阶段。当前目标:验证 libclang + 宏处理可行性(见 ARCHITECTURE §12)。

> 给弱 AI 的可消费资产(`PROMPT.md` / `prompts/`:如何为新宏写一条声明式规则)将在 V0
> 规则格式稳定后补齐。
