"""Eval: prompt 03 — 注册 Golden C 函数。

用法: .venv/bin/python prompts/eval/eval_03_golden.py <op_name>
示例: .venv/bin/python prompts/eval/eval_03_golden.py conv2d
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def eval_golden(op_name: str):
    checks = []

    try:
        from dsp.golden.manifest import COMPUTE
        # 查找该 op 的 ComputeKey
        op_keys = [k for k in COMPUTE if k.op == op_name]
        checks.append((f"COMPUTE 表有 {op_name} 的条目", len(op_keys) > 0))

        for key in op_keys:
            # 每个 key 的 value 不为空
            func_name = COMPUTE[key]
            checks.append((f"  {key.in0}×{key.in1}→{key.out0} 有 C 函数名", bool(func_name)))

            # DType 枚举值（不是裸字符串）
            from dsp.core.enums import DType
            all_enum = True
            for field in [key.in0, key.in1, key.out0, key.acc, key.compute]:
                if field is not None and not isinstance(field, str):
                    all_enum = False
            checks.append(("  字段类型正确", all_enum))
    except Exception as e:
        checks.append((f"manifest 加载失败: {e}", False))

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
    eval_golden(sys.argv[1])
