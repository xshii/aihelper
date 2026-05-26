"""规则的 schema(类型定义,框架的 port)。

框架只定义"规则长什么样";规则的**实例**(某个具体宏的描述符)住在项目的 rules/ 目录,
由 rules_loader 运行时加载。框架代码里不出现任何项目专属规则。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Arg:
    name: str
    role: str  # "id" | "in" | "out" | "meta"
    dtype: str | None = None
    shape_from: str | None = None  # 引用另一参数名作为 shape 来源


@dataclass
class Rule:
    macro: str
    op: str
    args: list[Arg] = field(default_factory=list)

    def _indices(self, role: str) -> list[int]:
        return [i for i, a in enumerate(self.args) if a.role == role]

    def input_indices(self) -> list[int]:
        return self._indices("in")

    def output_indices(self) -> list[int]:
        return self._indices("out")

    def id_index(self) -> int:
        ids = self._indices("id")
        return ids[0] if ids else -1


@dataclass
class Blacklist:
    skip_files: list[str] = field(default_factory=list)  # 按 basename 跳过整个文件
    skip_functions: list[str] = field(default_factory=list)  # 按函数名跳过其中的宏
