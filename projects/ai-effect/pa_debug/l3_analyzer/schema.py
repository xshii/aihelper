"""L3 解码 schema 的*类型*(端口)。项目写*实例*。Atom 嵌套 / Enum 暂不做(YAGNI)。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class U:
    bits: int  # 无符号位宽


@dataclass
class I:  # noqa: E742 - 语义上是 signed,与 U 对称
    bits: int  # 有符号位宽(补码)


@dataclass
class Ref:
    bits: int  # 地址位宽
    blob: str  # 外部内容名
    schema: Layout  # 取回内容用这套 Layout 递归解码(前向引用,future annotations 惰性)


@dataclass
class Field:
    name: str
    type: U | I | Ref


@dataclass
class Atom:
    name: str
    fields: list[Field]


@dataclass
class Layout:
    atoms: list[Atom]


@dataclass
class Dispatch:
    source: str  # 点路径,从 OpRecord.fields 取 op-kind
    table: dict[str, Layout]
