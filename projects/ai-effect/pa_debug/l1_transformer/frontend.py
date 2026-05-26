"""libclang 薄封装:解析 TU(开 detailed preprocessing record)、遍历宏实例、取 token。"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import clang.cindex as ci


class FuncSpan(NamedTuple):
    name: str
    start: int  # 函数定义起始字节
    end: int  # 函数定义结束字节(含右花括号)


# 机器相关的 libclang 路径不写死在框架里:bundled 加载失败时,从环境变量取覆盖路径。
_LIB_ENV = "PA_LIBCLANG_PATH"
_configured = False


def _ensure_lib() -> None:
    global _configured
    if _configured:
        return
    try:
        ci.Index.create()
    except ci.LibclangError:
        override = os.environ.get(_LIB_ENV)
        if not override:
            raise
        ci.Config.set_library_file(override)
    _configured = True


def parse_source(path: str, args: list[str] | None = None) -> ci.TranslationUnit:
    _ensure_lib()
    index = ci.Index.create()
    return index.parse(
        path,
        args=args or [],
        options=ci.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD,
    )


def macro_instantiations(tu: ci.TranslationUnit) -> Iterator[ci.Cursor]:
    for cur in tu.cursor.walk_preorder():
        if cur.kind == ci.CursorKind.MACRO_INSTANTIATION:
            yield cur


def function_spans(tu: ci.TranslationUnit, path: str) -> list[FuncSpan]:
    """主文件内的函数**定义**的源码区间(供 blacklist 判断宏属于哪个函数)。

    只取有函数体的定义;函数原型(如 stub header 里的声明)不计入。
    """
    target = Path(path).name
    spans: list[FuncSpan] = []
    for cur in tu.cursor.walk_preorder():
        if cur.kind != ci.CursorKind.FUNCTION_DECL or not cur.is_definition():
            continue
        extent = cur.extent
        if extent.start.file is None or Path(extent.start.file.name).name != target:
            continue
        spans.append(FuncSpan(cur.spelling, extent.start.offset, extent.end.offset))
    return spans
