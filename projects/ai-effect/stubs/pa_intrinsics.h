/* stubs/pa_intrinsics.h — 让 Clang 能解析含自定义宏的源码 */
#ifndef PA_INTRINSICS_H
#define PA_INTRINSICS_H

typedef struct { void* data; int ndim; int shape[8]; int dtype; } pa_tensor_t;

/* 保留参数列表的空展开:Clang 认得它是函数式宏,展开为空,不影响 AST 其余部分 */
#define PA_INSTR_CONV(op_id, in, w, out, ish, wsh, osh) do {} while (0)

/* 别名宏:源码里的同义写法,由 rules/isomorphisms.py 归一到 PA_INSTR_CONV */
#define PA_CONV(op_id, in, w, out, ish, wsh, osh) do {} while (0)

/* 另一种宏(示意:加载),arg 形状与 CONV 不同 */
#define PA_INSTR_LOAD(op_id, dst, src, shape) do {} while (0)

#endif
