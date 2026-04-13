"""项目根 conftest — 让 pytest 从任何 testpath 都能找到 dsp 包。

为什么在这里:
    op 测试文件放在 src/dsp/ops/<op>/test_<op>.py，pytest 不会自动把 src/
    加到 sys.path。tests/conftest.py 也只覆盖 tests/ 目录下的测试。
    这个 root-level conftest 被 pytest 作为所有 testpath 的共同祖先加载，
    保证不依赖 `pip install -e .` 也能跑测试（拷贝到新环境后直接可跑）。
"""
import sys
from pathlib import Path

_SRC = Path(__file__).parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
