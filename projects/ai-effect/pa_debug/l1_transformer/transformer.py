"""编排:解析→按规则匹配宏调用→生成 hook 调用 Edit→倒序应用→输出 .c + 站点清单。

V0:只 DUMP_AND_RUN(无 if 包裹),只处理语句位置的宏。生成的 hook 调用采用简化可读形式,
完整 pa_hook_ctx_t ABI 是 M3 的事。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .edits import Edit, apply_edits
from .frontend import FuncSpan, function_spans, parse_source
from .macro_extractor import MacroCall, find_macro_calls
from .rule import Blacklist, Rule


@dataclass
class Site:
    """L1 产出的插桩站点,供 L2/L3 关联 trace。"""

    site_id: str
    op: str
    macro: str
    file: str
    line: int
    args: list[str] = field(default_factory=list)


def _site_id(op: str, filename: str, line: int) -> str:
    return f"{op}@{filename}:{line}"


def _line_of(source_bytes: bytes, offset: int) -> int:
    return source_bytes[:offset].count(b"\n") + 1


def _indent_of(source_bytes: bytes, offset: int) -> str:
    return " " * (offset - (source_bytes.rfind(b"\n", 0, offset) + 1))


def _at_statement_position(source_bytes: bytes, start: int) -> bool:
    """宏是否"独立成句":跳过前导空白后,前一个非空白字符是 ; { } 或文件首。

    保守起见,表达式位置(如 x = MACRO(...))不插桩,避免生成非法 C(评审 H)。
    无大括号的控制流体(if (c) MACRO();)亦不处理,V0 建议加大括号。
    """
    i = start - 1
    while i >= 0 and source_bytes[i : i + 1] in (b" ", b"\t", b"\n", b"\r"):
        i -= 1
    return i < 0 or source_bytes[i : i + 1] in (b";", b"{", b"}")


def _enclosing_function(spans: list[FuncSpan], offset: int) -> str | None:
    for span in spans:
        if span.start <= offset < span.end:
            return span.name
    return None


def _hook_edits(call: MacroCall, rule: Rule, site_id: str, data: bytes) -> list[Edit]:
    in_args = [call.args[i] for i in rule.input_indices()]
    out_args = [call.args[i] for i in rule.output_indices()]
    indent = _indent_of(data, call.start_offset)
    before = f'pa_hook_before("{rule.op}", "{site_id}", ' + ", ".join(in_args) + ");\n" + indent
    after = "\n" + indent + f'pa_hook_after("{rule.op}", "{site_id}", ' + ", ".join(out_args) + ");"
    semi = data.find(b";", call.end_offset)
    after_pos = semi + 1 if semi >= 0 else call.end_offset
    return [
        Edit(offset=call.start_offset, length=0, replacement=before),
        Edit(offset=after_pos, length=0, replacement=after),
    ]


def instrument(
    path: str,
    rules: list[Rule],
    clang_args: list[str] | None = None,
    aliases: dict[str, str] | None = None,
    blacklist: Blacklist | None = None,
) -> tuple[str, list[Site]]:
    data = Path(path).read_bytes()
    filename = Path(path).name
    blacklist = blacklist or Blacklist()
    if filename in blacklist.skip_files:
        return data.decode(), []

    tu = parse_source(path, args=clang_args)
    skip_funcs = set(blacklist.skip_functions)
    spans = function_spans(tu, path) if skip_funcs else []

    edits: list[Edit] = []
    manifest: list[Site] = []
    for rule in rules:
        for call in find_macro_calls(tu, path, rule.macro, aliases):
            if not _at_statement_position(data, call.start_offset):
                continue
            if skip_funcs and _enclosing_function(spans, call.start_offset) in skip_funcs:
                continue
            line = _line_of(data, call.start_offset)
            site_id = _site_id(rule.op, filename, line)
            edits.extend(_hook_edits(call, rule, site_id, data))
            manifest.append(
                Site(
                    site_id=site_id,
                    op=rule.op,
                    macro=rule.macro,
                    file=filename,
                    line=line,
                    args=call.args,
                )
            )
    return apply_edits(data.decode(), edits), manifest
