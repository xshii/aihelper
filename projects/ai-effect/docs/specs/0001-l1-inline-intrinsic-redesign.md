# Spec 0001 — L1 设计:inline intrinsic + 两级插桩

- 状态:草案,待审 · 日期:2026-05-27
- 具体代码效果见配套 [0001-demo-walkthrough.md](0001-demo-walkthrough.md)。
- 标注:**【已定】**=用户已确认 · **【假设】**=待点头 · **【待定】**=信息缺口,实现前必补。
- **渐进式披露**:是什么→L0;做设计→L1;为什么→L2;要实现→L3。

---

## L0 · 一句话(TL;DR)

旧模型以为硬件指令是用户 `.c` 里的函数式宏调用,**错了**。真实 intrinsic 是**头文件里的 inline 函数**,
体内才调用无原型的**硬件宏**(`hac_3r` 等)。所以:

> **在调用点匹配 intrinsic 的 `CALL_EXPR`(第一级,知道名字)+ 在 inline 体内匹配硬件宏(第二级,纯码流只有 opid),按 `opid` 缝合。**

价值:从用户一行 `pa_conv(...)`,自动得到「**是谁 / 在哪个父函数 / 依赖谁 / 给硬件写了什么**」。
**V0 只做第一级**(已能产出 名字/父函数/公共头/依赖/指针·标量);第二级 words 列 V0.1。

---

## L1 · 核心设计

### 两级插桩 + 顺序关联(承重点)

| | 第一级 call-level | 第二级 macro-level(V0.1) |
|---|---|---|
| 在哪 | 用户 `.c` 的 `CALL_EXPR` 处 | inline 函数体内的硬件宏处(可在二/三级 inline,**沿调用链递归**) |
| 看得见 | intrinsic **名字** + 完整 Clang 类型 + `h->opid`(可靠) | **纯码流**:一串透传 word,**辨不出哪个是 opid** |
| 取参 | `Cursor.get_arguments()`(带类型) | `macro_extractor`+`arg_splitter` token 切 word |
| 产出 | 名字/父函数/公共头(含 opid)/指针/标量 | 每个 word 的运行时**原始值**(不解析语义) |

**关联靠执行顺序(bracketing),不靠在 word 里认 opid。** 传到宏层的全是透传值,无法可靠判断哪个是
opid。第一级记录是**外部锚点**:它之后、下一条第一级记录之前的所有 macro 记录,都归属这个算子。每条
记录带全局递增 `seq` 作顺序依据。opid 仍在第一级可靠读到(用于命名/依赖),但**不作两级 join key**。【已定】

### word 语义解析 = 独立离线工具

第二级只 dump **原始 word**;把 word → 语义(寄存器字段、是否含 opid 等)的解析做成**单独的离线工具**,
吃寄存器「PC 运行版」规格。理由:这种解析不可能在插桩期 / 宏层内部完成(那层只有透传值)。【已定】

### 第一级要点(V0 主体)

- **插在调用点**(用户 `.c`)之前,不进头文件 intrinsic 体内。
- **只 dump 一次**(调用前读输入);`after`(输出 buffer)留 V1。
- **直接生成 print,不走 hook 库**【已定】:transformer 在调用点前生成一条
  `if (pa_dump_enabled) <print_fn>("…JSONL…", 值…);`,把 名字/父函数/结构体展开字段/指针/标量
  拼成**一条记录**。因此 **V0 first-level 不需要 L2 hook 库**。
- **print 函数名可配**【已定】:`print_fn` 默认 `printf`;目标机换成平台自带的 printf 风格函数 ——
  生成代码**只换这个名字**,格式串不变。
- **结构体展开(泛化)**【已定】:**任意 typed 结构体** → 递归展开字段(**默认全读**,`struct_field_deny`
  黑名单排除无硬件支持/读不到的字段);`commopheader` 只是其中一类。
- 父函数名由 `function_spans` 给出(如 `layer3`)。

### 自动发现(intrinsic 非常多)【已定】

**头文件归属 + 正则黑白名单**:`FUNCTION_DECL` 落在指定 intrinsic 头文件集合 **且** 过名单 → 判为 intrinsic 站点。
名单必要,因头里有些 inline **不被外部调用**(纯内部辅助),仅靠头归属会过匹配。
配置:`intrinsic_headers` + `intrinsic_allow/deny: [regex]`。名单只过滤**第一级入口**,不挡第二级进辅助函数找宏。

### 角色推断(类型驱动,第一级)

| 参数类型 | 角色 | dump 行为 |
|---|---|---|
| 任意 typed 结构体 / 结构体指针(含 `commopheader`) | struct | 递归展开字段(默认全读,`struct_field_deny` 排除) |
| `void*` / 缓冲区指针 | opaque | 只打指针值(`%p`);**V0 不分 in/out** |
| 标量 | meta | 打值 |

**可读 dump 规则**:结构体→可读字段 · `void*`→指针值 · 标量/word/常数→运行时值。落盘 JSONL(见 ARCHITECTURE §6.2.4)。

### 运行时全局开关【已定】

`extern int pa_dump_enabled;`,每个 hook 首行 `if(!pa_dump_enabled) return;`。关闭近零开销 →
插桩后源码**可常驻**,git 撤销从「必须」降为「可选」(git_guard + marker 仍是安全网)。

### 红利:commopheader 直接给依赖图

`dep_ind`(位域)+ `aopid/bopid/copid`(A/B/C 单元前级算子 id)**本身就是算子依赖 DAG**:
- FR-4.4(上游传染 vs 本算子出错):沿上游 opid 回溯即可判定。
- FR-6.3(依赖图):依赖边 = `{opid → aopid/bopid/copid}`,直接成图。
把原 V2 的「静态依赖分析」降级为「读字段」。**【已定:数据来源;dep_ind 位→组件映射待定,Q2】**

---

## L2 · 决策(仅结果)

- **A** 对比用 paired per-op:硬件 dump 每算子输入+输出,离线把硬件真实输入喂 reference 比对;reference 在 L3(NumPy),V0 不在设备跑 ref。
- **B** V0 只 `DUMP_AND_RUN`;SKIP 类 + bisection 推 V1。
- **C** dump 语义靠**类型驱动推断 + 例外覆盖**。
- **D1** 在调用点匹配 `CALL_EXPR`(第一级)+ inline 体内匹配硬件宏(第二级)。
- **D2** 两级**按执行顺序(bracketing)关联**(全局 `seq`),不靠在 word 里认 opid(宏层是透传值辨不出);opid 仅第一级可靠读取,用于命名/依赖。word 语义解析交独立离线工具。
- **D3** `pa_dump_enabled` 全局门控,插桩可常驻。
- **D4** 第一级 V0 只 dump 一次,`after` 留 V1。
- **D5** 第一级插用户 `.c` 调用点,不改头文件 intrinsic 体。
- **D6** dump 由 transformer **直接生成 `print_fn` 调用**(默认 `printf`,可换平台函数名),一条 JSONL 记录;V0 first-level **无需 L2 hook 库**。
- **D7** 结构体展开泛化到**任意 typed 结构体**,默认全字段,`struct_field_deny` 排除不安全字段。

---

## L3 · 深水区(实现前再看)

### 配置点

`intrinsic_headers` · `intrinsic_allow/deny`(regex) · `common_header_type`(默认 `commopheader`) ·
`struct_field_deny`(各结构体不安全/读不到的字段黑名单,默认全展开) · `print_fn`(默认 `printf`,目标机换平台函数名) ·
`hardware_macros`(正则,如 `hac_\d+r`) · word 语义映射(独立离线工具) · 覆盖描述符 · `pa_dump_enabled`。

> 寄存器「PC 运行版」是 word 语义的来源,供**独立离线工具**把原始 word 解析成寄存器字段;插桩器不碰这层。

### 假设(待确认)

- **A3** V0 全局一个 `pa_dump_enabled`,粒度后扩。
- **A4** 头文件插桩 blast radius 由 git 守卫兜底即可。

### 待定 Q(实现前必补)

- **Q1** `commopheader` 字段类型/宽度(opid 位宽、aopid/bopid/copid 类型)。
- **Q2** `dep_ind` 位域的 位→依赖组件 映射。
- **Q4** 寄存器「PC 运行版」确切格式。

> 已答:**Q3** macro 紧跟其 intrinsic 的执行顺序**可靠** → bracketing 成立,L3 离线关联可建。
> **Q5** 硬件宏是 `hac_Nr` 家族(很多,主要按 word 数区分)→ `hardware_macros` 用**正则**(`hac_\d+r`)匹配,不逐个列;变长 word 已支持。
> **Q6** intrinsic 头文件**就地**插桩(git 守卫兜底 blast radius)。

### V0 切片(交给后续 plan 细化,本 spec 不锁定)

1. 第一级:CALL_EXPR 自动发现 + 类型角色推断 + dump 公共头(opid)/父函数/指针/标量。
2. 站点清单含 `kind=call` 与 opid。
3. 全局开关 + git 守卫复用;重建 fixtures(inline 头 + caller .c)。
4. 第二级(原始 words + 递归找宏 + 按 `seq`/顺序 bracketing 关联)列 **V0.1**,待 Q3/Q5/Q6 补齐;word 语义解析为独立离线工具。
