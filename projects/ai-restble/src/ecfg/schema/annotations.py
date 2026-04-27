"""YAML 注释的 @-annotation 解析器。

规则参考：docs/merge-spec.md §2.4

一条注释（去前导 ``#``）按顶层 ``;`` 切分段；每段若以 ``@<id>:`` 开头则为
annotation，否则视作人类 freeform 说明被工具忽略。括号 / 引号内的 ``;`` 不
算分段符。本解析器**不**识别 ref 区的 FK 记号（``<BaseName>.<field>``），
那是上层 schema loader 的职责。
"""
from __future__ import annotations

import re
from typing import List, NamedTuple

_ANNOTATION_RE = re.compile(r"^@([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", re.DOTALL)

_OPENERS = "([{"
_CLOSERS = ")]}"
_QUOTES = ("'", '"')


class Annotation(NamedTuple):
    """解析后的一条 @-annotation。value 保留原始字符串，不做二次解析。"""

    key: str
    value: str


class ParsedComment(NamedTuple):
    """一条注释的解析结果：annotations 清单 + freeform 人类说明清单。"""

    annotations: List[Annotation]
    freeform: List[str]


def parse_comment(text: str) -> ParsedComment:
    """把一条 YAML 注释（去 ``#``）解析成 annotations + freeform。

    空段跳过；括号/方括号/花括号/单引号/双引号嵌套内的 ``;`` 不切分。
    """
    annotations: List[Annotation] = []
    freeform: List[str] = []
    for segment in _split_top_level(text):
        seg = segment.strip()
        if not seg:
            continue
        match = _ANNOTATION_RE.match(seg)
        if match:
            annotations.append(Annotation(key=match.group(1), value=match.group(2).strip()))
        else:
            freeform.append(seg)
    return ParsedComment(annotations=annotations, freeform=freeform)


def _split_top_level(text: str) -> List[str]:
    """按顶层 ``;`` 切分；嵌套结构内的 ``;`` 保留。"""
    out: List[str] = []
    depth = 0
    in_quote = ""
    start = 0
    for i, ch in enumerate(text):
        if in_quote:
            if ch == in_quote:
                in_quote = ""
            continue
        if ch in _QUOTES:
            in_quote = ch
            continue
        if ch in _OPENERS:
            depth += 1
            continue
        if ch in _CLOSERS:
            depth -= 1
            continue
        if ch == ";" and depth == 0:
            out.append(text[start:i])
            start = i + 1
    out.append(text[start:])
    return out
