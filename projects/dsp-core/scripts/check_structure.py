"""结构校验 — 检查每个已注册算子的代码结构合规性。

规则（基于 prompt 02 的要求）：
1. ops/ 下每个算子文件有 @register_op 装饰器
2. ops/__init__.py 有对应的 import 和便捷函数
3. tests/ 下有对应的测试文件
4. 每个算子的函数参数有类型标注 (torch.Tensor)
"""

import ast
import re
import sys
from pathlib import Path

SRC = Path("src/dsp")
OPS_DIR = SRC / "ops"
TESTS_DIR = Path("tests")

# 跳过 __init__.py 和 __pycache__
SKIP_FILES = {"__init__.py"}


def main():
    ops_init = (OPS_DIR / "__init__.py").read_text()
    violations = []

    for f in sorted(OPS_DIR.glob("*.py")):
        if f.name in SKIP_FILES:
            continue
        op_name = f.stem
        src = f.read_text()

        # 1. 有 @register_op
        if "@register_op" not in src:
            violations.append((f.name, "缺少 @register_op 装饰器"))

        # 2. __init__.py import (支持 `import linear`, `import linear as _x`, 合并 import)
        import_pattern = rf"import\b.*\b{op_name}\b"
        if not re.search(import_pattern, ops_init):
            violations.append(("__init__.py", f"缺少 import {op_name}"))

        # 3. __init__.py 便捷函数
        func_pattern = rf"def\s+{op_name}\s*\("
        if not re.search(func_pattern, ops_init):
            violations.append(("__init__.py", f"缺少便捷函数 def {op_name}()"))

        # 4. 测试文件存在
        test_files = list(TESTS_DIR.glob(f"test_*{op_name}*")) + \
                     list(TESTS_DIR.glob(f"test_ops*"))
        if not test_files:
            violations.append((f.name, f"tests/ 下无 {op_name} 相关测试文件"))

        # 5. 函数参数有 torch.Tensor 标注
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name.startswith("_"):
                continue
            has_annotation = any(
                a.annotation is not None
                for a in node.args.args
                if a.arg != "self"
            )
            if not has_annotation:
                violations.append((f.name, f"函数 {node.name}() 参数无类型标注"))

    for fname, msg in violations:
        print(f"  {fname}: {msg}")

    if violations:
        print(f"\n  {len(violations)} structure violation(s)")
        sys.exit(1)
    else:
        print("  All operator structures valid")


if __name__ == "__main__":
    main()
