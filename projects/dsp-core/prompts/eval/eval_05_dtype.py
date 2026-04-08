"""Eval: prompt 05 — 定义 DSPDtype。

用法: .venv/bin/python prompts/eval/eval_05_dtype.py <dtype_name>
示例: .venv/bin/python prompts/eval/eval_05_dtype.py bfp16
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def eval_dtype(name: str):
    checks = []

    # 1. dtype.py 有实例定义
    dtype_src = Path("src/dsp/core/dtype.py").read_text()
    has_def = f'{name} = DSPDtype(' in dtype_src or f'name="{name}"' in dtype_src
    checks.append((f"dtype.py 有 {name} 定义", has_def))

    # 2. register_dtype 存在（不检查具体调用形式）
    checks.append(("dtype.py 有 register_dtype 调用", "register_dtype" in dtype_src))

    # 3. enums.py 有枚举值
    enums_src = Path("src/dsp/core/enums.py").read_text()
    enum_value = f'= "{name}"'
    checks.append(("enums.py 有枚举值", enum_value in enums_src))

    # 4. __init__.py 导出
    init_src = Path("src/dsp/core/__init__.py").read_text()
    checks.append(("core/__init__.py 导出", name in init_src))

    # 5. 运行时可访问
    try:
        import dsp
        dtype_obj = getattr(dsp.core, name, None)
        checks.append((f"dsp.core.{name} 可访问", dtype_obj is not None))
        if dtype_obj:
            checks.append(("name 字段正确", dtype_obj.name == name))
            checks.append(("torch_dtype 不为空", dtype_obj.torch_dtype is not None))
    except Exception as e:
        checks.append((f"运行时加载失败: {e}", False))

    _report(checks)


def _report(checks):
    all_pass = True
    for desc, ok in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  [{status}] {desc}")
    if all_pass:
        print("\nEVAL PASSED")
    else:
        print("\nEVAL FAILED")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <dtype_name>")
        sys.exit(1)
    eval_dtype(sys.argv[1])
