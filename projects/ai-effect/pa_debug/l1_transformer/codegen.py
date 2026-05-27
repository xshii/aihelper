"""生成 dump 代码 + 语句定位。dump 是一条受全局开关门控的 printf 风格调用,落一行 JSONL。"""

from __future__ import annotations

from .config import DiscoveryConfig
from .model import Arg

_STMT_BOUNDARY = (b";", b"{", b"}")
_WS = (b" ", b"\t", b"\n", b"\r")


def render_dump_call(op: str, fn: str | None, args: list[Arg], cfg: DiscoveryConfig) -> str:
    """一条 `if (flag) print_fn("…JSONL…", 值…);`。JSON 内的引号在 C 字面量里转义为 \\"。"""
    fmt = [f'{{\\"kind\\":\\"call\\",\\"op\\":\\"{op}\\",\\"fn\\":\\"{fn or "?"}\\"']
    values: list[str] = []
    for a in args:
        if a.role == "struct":
            obj = ",".join(f'\\"{f.name}\\":{f.fmt}' for f in a.fields or [])
            fmt.append(f',\\"{a.name}\\":{{{obj}}}')
            values.extend(f"({a.expr}){a.deref}{f.name}" for f in a.fields or [])
        elif a.role == "opaque":
            fmt.append(f',\\"{a.name}\\":\\"{a.fmt}\\"')
            values.append(f"(void*)({a.expr})")
        else:  # meta
            fmt.append(f',\\"{a.name}\\":{a.fmt}')
            values.append(a.expr)
    content = "".join(fmt) + "}\\n"
    prefix = f'if ({cfg.dump_flag}) {cfg.print_fn}("{content}"'
    body = f", {', '.join(values)}" if values else ""
    return f"{prefix}{body});"


def render_dump_macro(name: str, words: list[str], cfg: DiscoveryConfig) -> str:
    """一条 dump 原始 word 的 print。第二级不识别 opid(透传值),只落 word 数值。"""
    specs = ",".join("%u" for _ in words)
    content = f'{{\\"kind\\":\\"macro\\",\\"macro\\":\\"{name}\\",\\"words\\":[{specs}]}}\\n'
    prefix = f'if ({cfg.dump_flag}) {cfg.print_fn}("{content}"'
    values = ", ".join(f"(unsigned)({w})" for w in words)
    body = f", {values}" if values else ""
    return f"{prefix}{body});"


def statement_start(data: bytes, call_start: int) -> int:
    """包含该调用的语句的首个非空白字符偏移(向前找到 ;{} 边界,再跳过空白)。"""
    i = call_start - 1
    while i >= 0 and data[i : i + 1] not in _STMT_BOUNDARY:
        i -= 1
    j = i + 1
    while j < len(data) and data[j : j + 1] in _WS:
        j += 1
    return j


def indent_of(data: bytes, offset: int) -> str:
    line_start = data.rfind(b"\n", 0, offset) + 1
    k = line_start
    while k < len(data) and data[k : k + 1] in (b" ", b"\t"):
        k += 1
    return data[line_start:k].decode()
