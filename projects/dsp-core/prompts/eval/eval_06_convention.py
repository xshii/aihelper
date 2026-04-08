"""Eval: prompt 06 — 添加 OpConvention。

用法: .venv/bin/python prompts/eval/eval_06_convention.py <op_name>
示例: .venv/bin/python prompts/eval/eval_06_convention.py fft
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def eval_convention(op_name: str):
    checks = []

    # 1. op_convention.py 有对应类
    conv_src = Path("src/dsp/golden/op_convention.py").read_text()
    has_class = f'op="{op_name}"' in conv_src or f"'{op_name}'" in conv_src
    checks.append((f"op_convention.py 有 op='{op_name}'", has_class))

    # 2. 继承 OpConvention
    checks.append(("继承 OpConvention", "OpConvention" in conv_src))

    # 3. 运行时注册
    try:
        from dsp.golden.op_convention import get_convention
        conv = get_convention(op_name)
        checks.append(("get_convention() 返回实例", conv is not None))

        if conv:
            # 4. 有 output_shape 方法
            checks.append(("有 output_shape 方法", hasattr(conv, "output_shape")))
            # 5. 有 call_c_func 方法
            checks.append(("有 call_c_func 方法", hasattr(conv, "call_c_func")))
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
        print(f"用法: {sys.argv[0]} <op_name>")
        sys.exit(1)
    eval_convention(sys.argv[1])
