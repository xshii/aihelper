"""编排:解析 → 发现 intrinsic 调用 → 生成 dump 语句 Edit → 倒序应用 → 输出 .c + 站点清单。

V0 first-level:在每个 intrinsic 调用所在语句前插一条 `if (flag) print(...)`,dump
名字/父函数/结构体展开字段/指针/标量,落一行 JSONL。第二级(宏)与离线对照不在本里程碑。
"""

from __future__ import annotations

from pathlib import Path

from .codegen import indent_of, render_dump_call, statement_start
from .config import DiscoveryConfig
from .edits import Edit, apply_edits
from .frontend import FuncSpan, function_spans, iter_calls, parse_source
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
