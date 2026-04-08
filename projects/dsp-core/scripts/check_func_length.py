"""检查函数长度：非空非注释行 ≤ MAX_LINES。

嵌套函数独立计算，不计入外层函数行数。
"""

import ast
import pathlib
import sys

MAX_LINES = 50
SRC_DIR = pathlib.Path("src/dsp")


def own_lines(node, src_lines):
    """计算函数自身的非空非注释行数（排除嵌套函数体）。"""
    nested_ranges = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nested_ranges.append((child.lineno, child.end_lineno))

    count = 0
    for i in range(node.lineno - 1, node.end_lineno):
        line = src_lines[i].strip()
        if not line or line.startswith("#"):
            continue
        lineno = i + 1
        if any(start <= lineno <= end for start, end in nested_ranges):
            continue
        count += 1
    return count


def check():
    violations = []
    for f in sorted(SRC_DIR.rglob("*.py")):
        src = f.read_text()
        src_lines = src.splitlines()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                loc = own_lines(node, src_lines)
                if loc > MAX_LINES:
                    violations.append((loc, str(f), node.name, node.lineno))

    violations.sort(reverse=True)
    for loc, path, name, line in violations:
        print(f"  {loc:3d} lines  {path}:{line}  {name}")

    if violations:
        print(f"\n  {len(violations)} function(s) exceed {MAX_LINES} non-blank non-comment lines")
        sys.exit(1)
    else:
        print(f"  All functions <= {MAX_LINES} non-blank non-comment lines")


if __name__ == "__main__":
    check()
