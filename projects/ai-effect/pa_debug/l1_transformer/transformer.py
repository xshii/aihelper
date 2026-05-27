"""编排:解析 → 发现调用/硬件宏 → 生成受门控的 dump 语句 Edit → 倒序应用 → 输出 + 站点清单。

- instrument(第一级):用户 .c 的 intrinsic 调用点,dump 名字/父函数/结构体字段/指针/标量。
- instrument_macros(第二级):头文件 inline 体内的硬件宏,dump 原始 word(不识别 opid)。
两者都在所在语句前插一条 `if (pa_dump_enabled) print(...)`,落一行 JSONL。离线对照(L3)另算。
"""

from __future__ import annotations

from pathlib import Path

from .codegen import indent_of, render_dump_call, render_dump_macro, statement_start
from .config import DiscoveryConfig
from .edits import Edit, apply_edits
from .frontend import FuncSpan, function_spans, iter_calls, iter_macro_calls, parse_source
from .model import Site, SiteArg


def _line_of(data: bytes, offset: int) -> int:
    return data[:offset].count(b"\n") + 1


def _enclosing_function(spans: list[FuncSpan], offset: int) -> str | None:
    for span in spans:
        if span.start <= offset < span.end:
            return span.name
    return None


def instrument(
    path: str,
    cfg: DiscoveryConfig,
    clang_args: list[str] | None = None,
) -> tuple[str, list[Site]]:
    data = Path(path).read_bytes()
    filename = Path(path).name
    tu = parse_source(path, args=clang_args)
    spans = function_spans(tu, path)

    edits: list[Edit] = []
    sites: list[Site] = []
    for call in iter_calls(tu, data, cfg):
        fn = _enclosing_function(spans, call.start)
        stmt = statement_start(data, call.start)
        indent = indent_of(data, stmt)
        dump = render_dump_call(call.op, fn, call.args, cfg)
        edits.append(Edit(offset=stmt, length=0, replacement=f"{dump}\n{indent}"))
        sites.append(
            Site(
                kind="call",
                op=call.op,
                fn=fn,
                file=filename,
                line=_line_of(data, call.start),
                args=[SiteArg(a.name, a.role) for a in call.args],
            )
        )

    result = apply_edits(data.decode(), edits)
    if sites:
        result = f"extern int {cfg.dump_flag};\n{result}"
    return result, sites


def instrument_macros(
    path: str,
    cfg: DiscoveryConfig,
    clang_args: list[str] | None = None,
) -> tuple[str, list[Site]]:
    """第二级:对头文件 inline 体内的硬件宏插桩,dump 原始 word(不识别 opid)。"""
    data = Path(path).read_bytes()
    filename = Path(path).name
    tu = parse_source(path, args=["-x", "c", *(clang_args or [])])
    spans = function_spans(tu, path)

    edits: list[Edit] = []
    sites: list[Site] = []
    for mc in iter_macro_calls(tu, data, cfg.hardware_macros):
        fn = _enclosing_function(spans, mc.start)
        stmt = statement_start(data, mc.start)
        indent = indent_of(data, stmt)
        dump = render_dump_macro(mc.name, mc.words, cfg)
        edits.append(Edit(offset=stmt, length=0, replacement=f"{dump}\n{indent}"))
        sites.append(
            Site(
                kind="macro",
                op=mc.name,
                fn=fn,
                file=filename,
                line=_line_of(data, mc.start),
                args=[SiteArg(f"word{i}", "meta") for i in range(len(mc.words))],
            )
        )

    result = apply_edits(data.decode(), edits)
    if sites:
        result = f"extern int {cfg.dump_flag};\n{result}"
    return result, sites
