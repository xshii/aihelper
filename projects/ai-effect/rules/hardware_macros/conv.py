"""硬件宏 PA_INSTR_CONV 的插桩规则。

这是**项目专属配置**,不是框架代码。新增一种宏:复制本文件,改 macro/op/args 即可,
框架(pa_debug)无需改动。args 的 role 决定 dump 时把哪个指针当 input/output、哪个当 meta。
"""

from pa_debug.l1_transformer.rule import Arg, Rule

RULE = Rule(
    macro="PA_INSTR_CONV",
    op="CONV",
    args=[
        Arg("op_id", role="id"),
        Arg("in", role="in", dtype="f16", shape_from="ish"),
        Arg("w", role="in", dtype="f16", shape_from="wsh"),
        Arg("out", role="out", dtype="f16", shape_from="osh"),
        Arg("ish", role="meta"),
        Arg("wsh", role="meta"),
        Arg("osh", role="meta"),
    ],
)
