"""L1 配置(框架的 port):项目把这些值注入插桩器,框架不内置任何项目专属值。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DiscoveryConfig:
    """决定哪些调用算 intrinsic、怎么 dump。"""

    intrinsic_headers: list[str]  # 算 intrinsic 的头文件 basename
    allow: list[str] = field(default_factory=list)  # 名字白名单(正则;空=全放行)
    deny: list[str] = field(default_factory=list)  # 名字黑名单(正则;优先于白名单)
    struct_field_deny: dict[str, list[str]] = field(default_factory=dict)  # 结构体类型→不读的字段
    print_fn: str = "printf"  # dump 用的 printf 风格函数名(目标机换平台函数名)
    dump_flag: str = "pa_dump_enabled"  # 运行时全局开关变量名
