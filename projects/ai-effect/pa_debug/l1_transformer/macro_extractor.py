"""从 TU 提取指定宏的调用:宏名、参数列表、源码字节区间。"""

from __future__ import annotations

from dataclasses import dataclass

import clang.cindex as ci

from .arg_splitter import split_args
from .frontend import macro_instantiations


@dataclass
class MacroCall:
    name: str
    args: list[str]
    start_offset: int  # 宏名首字节
    end_offset: int  # 右括号后一字节


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def find_macro_calls(
    tu: ci.TranslationUnit,
    path: str,
    macro_name: str,
    aliases: dict[str, str] | None = None,
) -> list[MacroCall]:
    data = _read_bytes(path)
    aliases = aliases or {}
    calls: list[MacroCall] = []
    for cur in macro_instantiations(tu):
        if aliases.get(cur.spelling, cur.spelling) != macro_name:
            continue
        start = cur.extent.start.offset
        i = data.find(b"(", start)
        if i < 0:
            continue
        depth = 0
        j = i
        while j < len(data):
            ch = data[j : j + 1]
            if ch == b"(":
                depth += 1
            elif ch == b")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        arg_text = data[i + 1 : j].decode()
        calls.append(
            MacroCall(
                name=macro_name,
                args=split_args(arg_text),
                start_offset=start,
                end_offset=j + 1,
            )
        )
    return calls
