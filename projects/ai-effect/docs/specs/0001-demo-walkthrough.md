# Demo 走查 — 原始代码 vs 插桩后代码(请确认流程理解)

> 配套 [0001-l1-inline-intrinsic-redesign.md](0001-l1-inline-intrinsic-redesign.md)。
> 目的:用一个**具体、完整**的例子,让你核对我对插桩流程的理解对不对。
> **V0 已定:只交付第一级(call-level)**。第二级(macro-level)标为 **V0.1**,本走查一并画出但分开。
> 凡我拿不准的地方都标了 **❓请确认**。

---

## 0. 一图看懂流程

```
原始 .c/.h ──(pa-debug instrument 就地改写)──> 插桩后 .c/.h
                                                   │ 编译 + 跑(pa_dump_enabled=1)
                                                   ▼
                                              trace.jsonl  ──(离线按 opid join)──> 算子画像
```

---

## 1. 原始代码(系统给的,工具不改它的语义)

### 1.1 `pa_intrinsics.h` —— 系统自带头文件(很多 inline intrinsic)

```c
#ifndef PA_INTRINSICS_H
#define PA_INTRINSICS_H

/* 公共头:每个算子都带一份,opid 是关联键 */
typedef struct {
    unsigned opid;          /* 算子 id */
    unsigned dep_ind : 8;   /* 位域:依赖了哪些组件(位 → 组件映射 ❓待你给) */
    unsigned aopid;         /* A 计算单元的前级算子 id */
    unsigned bopid;         /* B 计算单元的前级算子 id */
    unsigned copid;         /* C 计算单元的前级算子 id */
} commopheader;

/* 硬件宏:函数式、无原型,展开后写寄存器。word0 里编了 opid */
#define MK_W0(opid)        (0x5A0000u | ((opid) & 0xFFFFu))   /* ❓opid 落 word0 低 16 位?待确认 */
#define hac_3r(w0, w1, w2) do { REG[0]=(w0); REG[1]=(w1); REG[2]=(w2); } while (0)

/* 二级辅助 inline:不被用户直接调用 → 黑白名单里 deny(不当 intrinsic 入口) */
static inline void _emit_conv(commopheader* h, int ish) {
    hac_3r(MK_W0(h->opid), ish, 0);   /* 硬件宏在这里;w0=含 opid 的宏, w1=值 ish, w2=常数 0 */
}

/* intrinsic:用户会调用 → 白名单命中(当作第一级入口) */
static inline void pa_conv(commopheader* h, void* in, void* w, void* out, int ish) {
    _emit_conv(h, ish);
}

#endif
```

### 1.2 `layer3.c` —— 用户模型代码(开发者写的,零改动)

```c
#include "pa_intrinsics.h"

extern void* in_buf;
extern void* w_buf;
extern void* out_buf;

void layer3(void) {
    commopheader h = { .opid = 42, .aopid = 41 };
    pa_conv(&h, in_buf, w_buf, out_buf, 56);
}
```

---

## 2. 工具怎么决策(插桩前的分析)

| 步骤 | 工具做什么 | 本例结果 |
|------|-----------|---------|
| 解析 | libclang 解析 `layer3.c`(带 stub/真头文件) | 得到 AST |
| 找调用 | 遍历 `CALL_EXPR` | 找到 `pa_conv(&h, ...)` |
| 自动发现 | 该调用的 `FUNCTION_DECL` 是否在 intrinsic 头 **且** 过正则名单 | `pa_conv` 在头里 ✓、allow 命中 ✓ → **是 intrinsic 入口** |
| | `_emit_conv` 虽在头里,但 deny 命中 | → **不当第一级入口**(但第二级会进它找宏) |
| 角色推断 | 按参数类型定角色(§5) | `commopheader* h`→header、`void* in/w/out`→opaque、`int ish`→meta |
| 读 opid | header 参数读 `h->opid` | opid 关联键就位 |
| 找父函数 | 记录调用点所在的外层函数(复用 `function_spans`) | 父函数 = `layer3` |

---

## 3. 插桩后代码(就地改写)

### 3.1 【V0 第一级】`layer3.c` —— 在调用点前生成一条 print

```c
/* pa-debug:instrumented — 还原用 git checkout */
extern int pa_dump_enabled;           /* ← 工具补:全局开关声明(1 行) */
#include "pa_intrinsics.h"

extern void* in_buf;
extern void* w_buf;
extern void* out_buf;

void layer3(void) {
    commopheader h = { .opid = 42, .aopid = 41 };
    if (pa_dump_enabled)              /* ← 生成的一条 print(printf 风格,函数名可配) */
        printf("{\"kind\":\"call\",\"op\":\"pa_conv\",\"fn\":\"layer3\","
               "\"h\":{\"opid\":%u,\"dep_ind\":%u,\"aopid\":%u,\"bopid\":%u,\"copid\":%u},"
               "\"in\":\"%p\",\"w\":\"%p\",\"out\":\"%p\",\"ish\":%d}\n",
               (&h)->opid,(&h)->dep_ind,(&h)->aopid,(&h)->bopid,(&h)->copid,
               (void*)in_buf,(void*)w_buf,(void*)out_buf,56);
    pa_conv(&h, in_buf, w_buf, out_buf, 56);
}
```

> **直接生成 print、不走 hook 库**:第一级在调用点前生成一条 `if(pa_dump_enabled) printf(...)`,
> 把 名字/父函数/结构体展开字段/指针/标量 拼成**一条 JSONL**。`commopheader` 这种结构体**展开字段**;
> `void*` 只打指针;标量打值。**目标机只需把 `printf` 换成平台 printf 风格函数名**(配置 `print_fn`)。
> 默认全字段展开,`struct_field_deny` 排除无硬件支持/读不到的字段。父函数 `layer3` 来自 `function_spans`。

### 3.2 【V0.1 第二级】`pa_intrinsics.h` —— 递归进 `_emit_conv` 给硬件宏插 hook

```c
static inline void _emit_conv(commopheader* h, int ish) {
    if (pa_dump_enabled)        /* ← 同样生成 print:只 dump 原始 word,不在此层认 opid */
        printf("{\"kind\":\"macro\",\"macro\":\"hac_3r\",\"words\":[%u,%u,%u]}\n",
               (unsigned)MK_W0(h->opid), (unsigned)ish, 0u);
    hac_3r(MK_W0(h->opid), ish, 0);
}
```

> 生成的 print **对每个 word 求值**(word 可能是宏/值/常数),只落**原始 word**。
> **本质**:第二级是**纯透传码流**——看不到语义,也**辨不出哪个值是 opid**。所以**不在此层认 opid**;
> 这条 macro 记录**按执行顺序**归属到它前面那条 call 记录(`pa_conv`)。word → 语义(含是否有 opid)
> 由**独立离线工具**按寄存器「PC 运行版」解析。宏入参除数据 word 外可能还带其他东西(❓待你给)。
> **❓请确认 B**:第二级要就地改**头文件**(影响所有 includer),git 守卫照样拦脏文件,但 blast
> radius 比改 .c 大。可接受?还是生成头文件副本 + 改 include 路径?

---

## 4. 运行时输出(`pa_dump_enabled=1` 时落盘)

`trace.jsonl`:

```jsonl
{"kind":"call","op":"pa_conv","fn":"layer3","h":{"opid":42,"dep_ind":0,"aopid":41,"bopid":0,"copid":0},"in":"0x7ffe0000a0","w":"0x7ffe0000c8","out":"0x7ffe0000f0","ish":56}
{"kind":"macro","macro":"hac_3r","words":[5898282,56,0]}
```

> macro 记录**没有 opid**:它**按执行顺序**归属到紧邻其前的 call 记录(`pa_conv`)。
> 关闭开关(`pa_dump_enabled=0`)时,`if` 为假直接跳过 print,**近零开销**;插桩后源码可常驻、
> 不必每次 `git checkout` 还原(git 仍是安全网)。
> `5898282`=`0x5A002A`=`MK_W0(42)` —— 但**插桩器不解析它**,留给离线工具。

---

## 5. 离线:按 opid join → 完整算子画像

```
opid = 42
├─ 名字      : pa_conv                 (来自第一级,第二级看不见)
├─ 父函数    : layer3                  (调用点所在的模型函数)
├─ 公共头    : opid=42, aopid=41        (上游算子 41 → 依赖边 42→41)
├─ 指针入参  : in=0x..a0, w=0x..c8, out=0x..f0
├─ 标量      : ish=56
└─ 寄存器写  : hac_3r words=[0x5A002A, 56, 0]   (纯码流,按执行顺序归属到本算子;第二级=V0.1)
```

**价值**:从用户一行 `pa_conv(...)`,自动得到「**是谁 / 依赖谁 / 给硬件写了什么**」。
- 「依赖谁」(aopid)→ 喂 FR-4.4(上游传染 vs 本算子出错)和 FR-6.3(依赖图)。
- 「给硬件写什么」(words)→ 喂逐算子对照(第二级,V0.1)。

---

## 6. 请你核对的关键点(✅=你已确认)

1. ✅ 第一级匹配**用户 `.c` 里对 inline intrinsic 的普通函数调用(CALL_EXPR)**,不是宏。
2. ✅ 第一级**插在调用点(用户 `.c`),不插进头文件 intrinsic 体内**——你说这样可能更好。
3. ✅ **只 dump 一次**:V0 只有 `void*` 指针,调用前后相同,`after` 重复打印冗余;待 V1 能 dump
   buffer 内容时再加 `after`。
4. ✅ trace 记录**父函数名**(`layer3`)。
5. ✅ 第二级是**纯透传码流**,**辨不出哪个是 opid** → 两级**按执行顺序关联**(不靠在 word 里认 opid);
   word 语义解析交**独立离线工具**;宏入参除 word 外还带其他东西。
6. 自动发现 = **头文件归属 + 正则黑白名单**;`_emit_conv` 这类内部辅助 deny,不当第一级入口 —— 对吗?
7. 角色按类型:`commopheader*`→读子成员、`void*`→只打指针、标量→打值 —— 对吗?
8. 第二级硬件宏可能在二/三级 inline 里,要沿调用链递归找 —— 对吗?最深几级?
9. 全局开关 `pa_dump_enabled` 控制打不打印 —— 对吗?
10. **V0 只做第一级**(名字/父函数/公共头/指针/标量),第二级 words 留 V0.1 —— 这样切对吗?

**仍要你补的硬数据**:❓macro 紧跟 intrinsic 的执行顺序是否可靠(bracketing 前提) ❓`dep_ind` 位→组件映射
❓宏 word 之外的"其他东西"是什么 ❓inline 调用链最深几级。
