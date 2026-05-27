"""libclang 薄封装:解析 TU(开 detailed preprocessing record)、遍历宏实例、取 token。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple

import clang.cindex as ci

from .config import DiscoveryConfig
from .discovery import is_intrinsic
from .model import Arg, Call, FieldSpec

_UNSIGNED = {
    ci.TypeKind.UCHAR,
    ci.TypeKind.USHORT,
    ci.TypeKind.UINT,
    ci.TypeKind.ULONG,
    ci.TypeKind.ULONGLONG,
}
_FLOATING = {ci.TypeKind.FLOAT, ci.TypeKind.DOUBLE, ci.TypeKind.LONGDOUBLE}


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


def _fmt_for(t: ci.Type) -> str:
    kind = t.get_canonical().kind
    if kind == ci.TypeKind.POINTER:
        return "%p"
    if kind in _FLOATING:
        return "%f"
    if kind in _UNSIGNED:
        return "%u"
    return "%d"


def _fields(record: ci.Type) -> list[FieldSpec]:
    decl = record.get_declaration()
    return [
        FieldSpec(f.spelling, _fmt_for(f.type))
        for f in decl.get_children()
        if f.kind == ci.CursorKind.FIELD_DECL
    ]


def _arg_of(name: str, expr: str, ptype: ci.Type) -> Arg:
    can = ptype.get_canonical()
    if can.kind == ci.TypeKind.POINTER:
        pointee = can.get_pointee().get_canonical()
        if pointee.kind == ci.TypeKind.RECORD:
            return Arg(name, expr, "struct", fields=_fields(pointee), deref="->")
        return Arg(name, expr, "opaque", fmt="%p")
    if can.kind == ci.TypeKind.RECORD:
        return Arg(name, expr, "struct", fields=_fields(can), deref=".")
    return Arg(name, expr, "meta", fmt=_fmt_for(ptype))


def _arg_text(data: bytes, cur: ci.Cursor) -> str:
    extent = cur.extent
    return data[extent.start.offset : extent.end.offset].decode()


def iter_calls(tu: ci.TranslationUnit, data: bytes, cfg: DiscoveryConfig) -> list[Call]:
    """主文件里所有 intrinsic 调用(经发现过滤),参数角色由类型推断。"""
    calls: list[Call] = []
    for cur in tu.cursor.walk_preorder():
        if cur.kind != ci.CursorKind.CALL_EXPR:
            continue
        ref = cur.referenced
        if ref is None:
            continue
        decl_file = ref.location.file.name if ref.location.file else None
        if not is_intrinsic(decl_file, ref.spelling, cfg):
            continue
        args = [
            _arg_of(param.spelling, _arg_text(data, arg), param.type)
            for arg, param in zip(cur.get_arguments(), ref.get_arguments(), strict=False)
        ]
        calls.append(
            Call(
                op=ref.spelling,
                decl_file=decl_file,
                start=cur.extent.start.offset,
                end=cur.extent.end.offset,
                args=args,
            )
        )
    return calls
