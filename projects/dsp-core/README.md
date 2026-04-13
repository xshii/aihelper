# dsp-core

> DSP 芯片验证框架 — torch-like API，多模式验证，golden C 桥接。

## Quick Start

```bash
cd projects/dsp-core
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make ci                # lint + 架构检查 + 81 tests
make smoke             # E2E generate_input + use_input
make build-golden      # 编译 C++ 绑定（需要 pybind11 + cmake）
```

```python
import dsp

def main():
    x = dsp.data.randn(4, 8, dtype=dsp.core.iq16)
    w = dsp.data.randn(8, 4, dtype=dsp.core.iq16)
    b = dsp.data.randn(1, 4, dtype=dsp.core.iq16)
    return dsp.ops.linear(x, w, b)

dsp.context.run(main)
```

## 文件结构

```
dsp-core/
├── src/dsp/
│   ├── core/       DSPDtype + DSPTensor + Enums + Errors
│   ├── golden/     C++ 封装（manifest + call + dispatch + pybind11 绑定）
│   ├── data/       DataPipe 链式 API + 工厂函数 + 比数报告
│   ├── ops/        @register_op + linear, layernorm
│   ├── context/    模式切换 + 验证循环 + run()
│   └── config.py   全局配置
├── golden_c/       硬件团队提供（.h + .so）
├── tests/          81 tests（UT/IT/ST 分级）
├── examples/       matmul_example.py
└── prompts/        6 个弱 AI prompt
```

## 弱 AI 投喂手册

见 [PROMPT.md](PROMPT.md)。
