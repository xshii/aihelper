"""等价类(isomorphism):别名宏 → 规范宏。

源码里同义的不同写法,在匹配前归一到规范宏名,避免每个别名都写一条规则。
这是**项目专属配置**,不是框架代码。键是源码里出现的别名,值是 rules/ 里有规则的规范宏。
"""

ALIASES = {
    "PA_CONV": "PA_INSTR_CONV",
    "PA_CONV2D": "PA_INSTR_CONV",
}
