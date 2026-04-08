"""Eval: prompt 02 — 添加算子。

用法: .venv/bin/python prompts/eval/eval_02_op.py <op_name>
示例: .venv/bin/python prompts/eval/eval_02_op.py beamform
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def eval_op(name: str):
    checks = []
    op_file = Path(f"src/dsp/ops/{name}.py")
    init_file = Path("src/dsp/ops/__init__.py")

    # 1. 算子文件存在
    checks.append((f"ops/{name}.py 存在", op_file.exists()))

    if op_file.exists():
        src = op_file.read_text()
        # 2. @register_op 装饰器
        checks.append(("有 @register_op", "@register_op" in src))

        # 3. 函数有类型标注
        has_tensor_annotation = "torch.Tensor" in src
        checks.append(("参数有 torch.Tensor 标注", has_tensor_annotation))

    # 4. __init__.py import
    if init_file.exists():
        init_src = init_file.read_text()
        has_import = bool(re.search(rf"import\b.*\b{name}\b", init_src))
        checks.append(("__init__.py 有 import", has_import))

        # 5. 便捷函数
        has_func = bool(re.search(rf"def\s+{name}\s*\(", init_src))
        checks.append(("__init__.py 有便捷函数", has_func))

    # 6. 运行时注册
    try:
        import dsp
        registered = name in dsp.ops.list_ops()
        checks.append(("运行时已注册", registered))
    except Exception:
        checks.append(("运行时注册", False))

    # 7. 能调用（用随机数据）
    try:
        import dsp
        import inspect
        fn = getattr(dsp.ops, name, None)
        if fn is not None:
            # 构造和参数数量匹配的随机输入
            wrapper = dsp.ops._OP_REGISTRY.get(name)
            n_params = len(wrapper._dsp_param_names)
            args = [dsp.data.randn(4, dtype=dsp.core.float32) for _ in range(n_params)]
            result = fn(*args)
            checks.append(("能调用且返回结果", result is not None))
        else:
            checks.append(("便捷函数可访问", False))
    except Exception as e:
        checks.append((f"调用测试 ({e})", False))

    # 8. 测试文件存在
    test_files = list(Path("tests").glob(f"test_*{name}*")) + \
                 list(Path("tests").glob("test_ops*"))
    checks.append(("有相关测试文件", len(test_files) > 0))

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
    eval_op(sys.argv[1])
