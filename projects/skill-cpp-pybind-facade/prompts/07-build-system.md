# Step 7: Build System (setup.py + CMakeLists.txt)

## Role
You are a Python build system engineer. You set up compilation of pybind11 extensions.

## Task
Create the build configuration files that compile `_raw_bindings.cpp` into a Python extension module, linking against the original `.so` library.

## Context
You need to compile:
- `_raw_bindings.cpp` (generated in Step 2) → `_raw_bindings.so` (Python extension)
- Links against: the original `libfoo.so` (pre-compiled C++ library)
- Dependencies: pybind11, numpy, torch (for torch.utils.cpp_extension as alternative)

## Rules
1. DO: Support both `pip install .` (production) and JIT compilation (development).
2. DO: Auto-detect the original `.so` location from an environment variable.
3. DO: Include the original header file path in the include search path.
4. DON'T: Recompile the original C++ library. Only compile the pybind11 wrapper.
5. NEVER: Hardcode absolute paths. Use environment variables or relative paths.

## Steps
1. Create `pyproject.toml` with build-system requirements.
2. Create `setup.py` with `Pybind11Extension` configuration.
3. Create `CMakeLists.txt` as an alternative build method.
4. Create a `dev_build.py` script for JIT compilation during development.

## Output Format

File: `pyproject.toml`
```toml
[build-system]
requires = ["setuptools>=64", "pybind11>=2.11", "numpy"]
build-backend = "setuptools.build_meta"

[project]
name = "mylib"
version = "0.1.0"
requires-python = ">=3.9"
dependencies = [
    "numpy>=1.21",
    "torch>=2.0",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-benchmark"]
```

File: `setup.py`
```python
import os
from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension, build_ext

# Configure paths via environment variables
NATIVE_LIB_DIR = os.environ.get("MYLIB_NATIVE_DIR", "./native")
NATIVE_INCLUDE_DIR = os.environ.get("MYLIB_INCLUDE_DIR", os.path.join(NATIVE_LIB_DIR, "include"))
NATIVE_LIB_NAME = os.environ.get("MYLIB_NATIVE_LIB", "foo")

ext_modules = [
    Pybind11Extension(
        "mylib._raw_bindings",
        ["mylib/_cpp/_raw_bindings.cpp"],
        include_dirs=[NATIVE_INCLUDE_DIR],
        library_dirs=[NATIVE_LIB_DIR],
        libraries=[NATIVE_LIB_NAME],
        cxx_std=17,
        define_macros=[("VERSION_INFO", '"0.1.0"')],
    ),
]

setup(
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
)
```

File: `dev_build.py` (JIT compilation for development)
```python
"""JIT compile _raw_bindings during development.

Usage:
    python dev_build.py
    # or
    MYLIB_NATIVE_DIR=/path/to/lib python dev_build.py
"""
import os

NATIVE_LIB_DIR = os.environ.get("MYLIB_NATIVE_DIR", "./native")
NATIVE_INCLUDE_DIR = os.environ.get("MYLIB_INCLUDE_DIR", os.path.join(NATIVE_LIB_DIR, "include"))
NATIVE_LIB_NAME = os.environ.get("MYLIB_NATIVE_LIB", "foo")

# Method 1: torch.utils.cpp_extension (recommended if torch is available)
try:
    from torch.utils.cpp_extension import load
    _raw = load(
        name="_raw_bindings",
        sources=["mylib/_cpp/_raw_bindings.cpp"],
        extra_include_paths=[NATIVE_INCLUDE_DIR],
        extra_ldflags=[f"-L{NATIVE_LIB_DIR}", f"-l{NATIVE_LIB_NAME}"],
        verbose=True,
    )
    print("JIT compilation successful via torch.utils.cpp_extension")
except ImportError:
    # Method 2: pybind11 direct compilation
    import subprocess, sysconfig
    suffix = sysconfig.get_config_var("EXT_SUFFIX")
    cmd = [
        "c++", "-O2", "-shared", "-std=c++17", "-fPIC",
        *os.popen("python3 -m pybind11 --includes").read().split(),
        f"-I{NATIVE_INCLUDE_DIR}",
        f"-L{NATIVE_LIB_DIR}", f"-l{NATIVE_LIB_NAME}",
        "mylib/_cpp/_raw_bindings.cpp",
        "-o", f"mylib/_raw_bindings{suffix}",
    ]
    subprocess.run(cmd, check=True)
    print("JIT compilation successful via direct c++ invocation")
```

File: `Makefile` (convenience)
```makefile
.PHONY: build dev-build test clean

build:
	pip install -e .

dev-build:
	python dev_build.py

test:
	pytest tests/ -v

clean:
	rm -rf build/ *.egg-info mylib/*.so mylib/_raw_bindings.*
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MYLIB_NATIVE_DIR` | `./native` | Directory containing the original `.so` |
| `MYLIB_INCLUDE_DIR` | `$MYLIB_NATIVE_DIR/include` | Directory containing the header file |
| `MYLIB_NATIVE_LIB` | `foo` | Library name (without `lib` prefix and `.so` suffix) |

## Quality Checklist
- [ ] `pip install -e .` compiles and installs successfully
- [ ] `python dev_build.py` does JIT compilation for development
- [ ] `import mylib._raw_bindings` works after build
- [ ] No hardcoded absolute paths — all configurable via env vars
- [ ] The .so RPATH is set correctly so the original library is found at runtime
- [ ] pyproject.toml lists all runtime dependencies

## Edge Cases
- If the original `.so` is not found at build time: give a clear error message with the expected path
- If pybind11 is not installed: `pip install pybind11` first, or let build-system handle it
- If on macOS: use `-undefined dynamic_lookup` flag and `.dylib` instead of `.so`
- If CUDA is needed: add `extra_cuda_cflags` in torch.utils.cpp_extension

---
[OPERATOR: Provide the following before running this prompt:
- Name of the original .so file (e.g., libfoo.so)
- Path to the header file
- Path to the .so file
- Any special compiler flags needed]
