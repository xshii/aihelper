"""Eval: prompt 01 — 添加 Codec。

用法: .venv/bin/python prompts/eval/eval_01_codec.py <dtype_name>
示例: .venv/bin/python prompts/eval/eval_01_codec.py bfp16
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def eval_codec(name: str):
    checks = []

    # 1. codec.py 中有对应的类定义
    codec_src = Path("src/dsp/core/codec.py").read_text()
    class_pattern = f"class {name.upper().replace('-', '')}Codec"
    # 也尝试驼峰: Bfp16Codec
    camel = name.capitalize() + "Codec"
    found_class = class_pattern.lower() in codec_src.lower() or camel in codec_src
    checks.append(("codec.py 有 Codec 类", found_class))

    # 2. 继承 GoldenCCodec
    checks.append(("继承 GoldenCCodec", "GoldenCCodec" in codec_src))

    # 3. 运行时注册生效
    try:
        import dsp
        from dsp.core.codec import get_codec
        dtype_obj = getattr(dsp.core, name, None)
        if dtype_obj is None:
            checks.append((f"dsp.core.{name} 存在", False))
        else:
            codec = get_codec(dtype_obj)
            checks.append((f"get_codec({name}) 返回 Codec", codec is not None))
    except Exception as e:
        checks.append(("运行时注册", False))

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
    eval_codec(sys.argv[1])
