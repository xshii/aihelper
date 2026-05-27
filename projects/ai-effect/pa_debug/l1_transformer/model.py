"""L1 数据模型(clang 无关):frontend 产出 Call,transformer 产出 Site。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Role = Literal["struct", "opaque", "meta"]


@dataclass
class FieldSpec:
    name: str
    fmt: str  # printf 转换符:%u / %d / %p / %f


@dataclass
class Arg:
    name: str  # 形参名
    expr: str  # 实参源码文本(&h / in_buf / 56)
    role: Role
    fmt: str | None = None  # opaque/meta 的转换符
    fields: list[FieldSpec] | None = None  # struct 展开字段
    deref: str = "->"  # 指针结构体用 ->,值结构体用 .


@dataclass
class Call:
    op: str  # intrinsic 名
    decl_file: str | None  # 其 FUNCTION_DECL 定义所在文件
    start: int  # 调用表达式起始字节
    end: int
    args: list[Arg] = field(default_factory=list)


@dataclass
class MacroCall:
    name: str  # 硬件宏名
    start: int  # 宏名起始字节
    words: list[str] = field(default_factory=list)  # 各 word 的源码文本(原始,不解析语义)


@dataclass
class SiteArg:
    name: str
    role: Role


@dataclass
class Site:
    kind: str  # "call"
    op: str
    fn: str | None  # 调用点所在父函数
    file: str
    line: int
    args: list[SiteArg] = field(default_factory=list)
