"""硬件宏 PA_INSTR_LOAD 的插桩规则(示意:DRAM→片上 加载)。

形状与 CONV 不同(1 输入 1 输出 1 meta),用来证明规则 schema 可泛化到不同 arity——
加这种宏只需新增本文件,框架(pa_debug)零改动。
"""

from pa_debug.l1_transformer.rule import Arg, Rule

RULE = Rule(
    macro="PA_INSTR_LOAD",
    op="LOAD",
    args=[
        Arg("op_id", role="id"),
        Arg("dst", role="out", dtype="f16", shape_from="shape"),
        Arg("src", role="in", dtype="f16", shape_from="shape"),
        Arg("shape", role="meta"),
    ],
)
