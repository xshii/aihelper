"""校验 prompt 文件中引用的路径是否存在。

扫描 prompts/*.md 和 PROMPT.md，提取 `src/...` 和 `tests/...` 路径引用，
检查文件是否存在。防止代码重构后 prompt 漂移。
"""

import re
import sys
from pathlib import Path

PROMPT_DIR = Path("prompts")
ROOT = Path(".")

# 匹配 backtick 或行首的路径引用
PATH_PATTERN = re.compile(r'`((?:src|tests|examples|golden_c)/[^`\s]+)`')


def check():
    violations = []
    md_files = list(PROMPT_DIR.glob("*.md")) + [ROOT / "PROMPT.md"]

    for md in md_files:
        if not md.exists():
            continue
        text = md.read_text()
        for match in PATH_PATTERN.finditer(text):
            ref_path = match.group(1)
            # 去掉尾部标点
            ref_path = ref_path.rstrip(".,;:)")
            # 跳过模板占位符（含 < > 的路径）
            if "<" in ref_path or ">" in ref_path:
                continue
            if not (ROOT / ref_path).exists():
                violations.append((md.name, ref_path))

    for md_name, ref in violations:
        print(f"  {md_name}: 引用路径不存在 → {ref}")

    if violations:
        print(f"\n  {len(violations)} broken reference(s) in prompts")
        sys.exit(1)
    else:
        print("  All prompt references valid")


if __name__ == "__main__":
    check()
