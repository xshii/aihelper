"""从硬件宏调用里提取 word 实参。函数式宏无原型,只能 token 级切分。"""

from __future__ import annotations

_OPEN = (b"(", b"[", b"{")
_CLOSE = (b")", b"]", b"}")


def extract_words(data: bytes, name_start: int) -> list[str]:
    """`name_start` 指向宏名;找其后第一个 `(`,平衡扫描到匹配 `)`,按顶层逗号切 word。"""
    open_paren = data.index(b"(", name_start)
    words: list[bytes] = []
    depth = 0
    arg_start = open_paren + 1
    quote = b""
    i = open_paren
    while i < len(data):
        ch = data[i : i + 1]
        if quote:
            if ch == b"\\":
                i += 2
                continue
            if ch == quote:
                quote = b""
        elif ch in (b'"', b"'"):
            quote = ch
        elif ch in _OPEN:
            depth += 1
        elif ch in _CLOSE:
            depth -= 1
            if depth == 0:
                words.append(data[arg_start:i])
                break
        elif ch == b"," and depth == 1:
            words.append(data[arg_start:i])
            arg_start = i + 1
        i += 1
    return [w.strip().decode() for w in words if w.strip()]
