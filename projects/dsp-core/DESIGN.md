# Software Design: C++ Flat API → Pythonic Facade with Torch Frontend

## 1. Problem Statement

### 你面对的 C++ API 长这样

```cpp
// === 类型转换：M*(M-1) 个平铺函数 ===
int convert_TypeA_to_TypeB(const TypeA* src, TypeB* dst, int count);
int convert_TypeA_to_TypeC(const TypeA* src, TypeC* dst, int count);
int convert_TypeB_to_TypeA(const TypeB* src, TypeA* dst, int count);
int convert_TypeB_to_TypeC(const TypeB* src, TypeC* dst, int count);
int convert_TypeC_to_TypeA(const TypeC* src, TypeA* dst, int count);
int convert_TypeC_to_TypeB(const TypeC* src, TypeB* dst, int count);
// ... M+1 种类型 → M*(M-1) 个函数

// === 计算接口：N 种计算 × K 种类型组合 ===
int compute_add_TypeA_TypeA(const TypeA* a, const TypeA* b, TypeA* out, int n);
int compute_add_TypeA_TypeB(const TypeA* a, const TypeB* b, TypeB* out, int n);
int compute_mul_TypeA_TypeA(const TypeA* a, const TypeA* b, TypeA* out, int n);
int compute_mul_TypeB_TypeC(const TypeB* a, const TypeC* b, TypeC* out, int n);
// ... N 种运算 × K 种类型组合
```

### 为什么这很糟糕

- **组合爆炸**: 5 种类型 = 20 个转换函数 + N*25 个计算函数
- **不可维护**: 头文件几千行，无法一屏看完
- **AI 不友好**: 弱 AI 看到 200 个函数签名会迷失
- **无类型安全**: 调用方必须自己判断该调哪个函数

### 我们要做到什么

```python
# 用户看到的（Layer 0）
import mylib
result = mylib.compute("add", tensor_a, tensor_b)

# 用户看到的（Layer 1）
result = mylib.compute("add", tensor_a, tensor_b, out_dtype=mylib.TypeC)
converted = mylib.convert(tensor_a, target_type=mylib.TypeB)
```

---

## 2. Architecture

```
┌────────────────────────────────────────────────────────┐
│  User Code                                             │
│  result = mylib.compute("add", tensor_a, tensor_b)     │
└───────────────────────┬────────────────────────────────┘
                        │
┌───────────────────────▼────────────────────────────────┐
│  Layer 0: api.py  (Torch Frontend)                     │
│  - torch.Tensor in → torch.Tensor out                  │
│  - dtype inference                                     │
│  - DLPack / data_ptr zero-copy                         │
└───────────────────────┬────────────────────────────────┘
                        │
┌───────────────────────▼────────────────────────────────┐
│  Layer 1: facade.py  (Type Dispatch)                   │
│  - Registry: (op, dtype_a, dtype_b) → C++ func         │
│  - Single convert() / compute() entry point            │
│  - Output type inference rules                         │
└───────────────────────┬────────────────────────────────┘
                        │
┌───────────────────────▼────────────────────────────────┐
│  Layer 1.5: preprocessor.py  (Pluggable Preprocessing) │
│  - PreprocessorRegistry: dtype → preprocessor          │
│  - Hook point for external preprocessing               │
│  - Runs BEFORE data enters C++ compute                 │
└───────────────────────┬────────────────────────────────┘
                        │
┌───────────────────────▼────────────────────────────────┐
│  Layer 2: _raw_bindings (pybind11 Module)              │
│  - Mechanical 1:1 wrapping of every C++ function       │
│  - Auto-generated from header parsing                  │
│  - Thin: no logic, just type bridging                  │
└───────────────────────┬────────────────────────────────┘
                        │
┌───────────────────────▼────────────────────────────────┐
│  Layer 3: libfoo.so  (Original C++ Library)            │
│  - The ugly flat API we do NOT modify                  │
└────────────────────────────────────────────────────────┘
```

---

## 3. Key Design Decisions

### 3.1 Binding Strategy: pybind11 + Code Generation

**不要手写每个 binding。** 用代码生成器解析头文件，自动产出 pybind11 代码。

```
header.h  →  [header_parser.py]  →  function_table.json  →  [binding_generator.py]  →  _raw_bindings.cpp
```

**为什么不用 ctypes/cffi？**
- pybind11 与 torch C++ extension 生态无缝集成
- 支持 `torch::Tensor` 作为参数类型
- 编译期类型检查

**为什么不用 nanobind？**
- nanobind 更轻量，也可以用，但 pybind11 生态更成熟、文档更多，弱 AI 更容易找到参考
- 如果性能敏感（binding overhead 是瓶颈），可以换 nanobind，API 几乎兼容

### 3.2 Registry Pattern: 消除 if-else 链

```python
# BAD: 弱 AI 容易写出这种代码
def convert(src, target_type):
    if isinstance(src, TypeA) and target_type == TypeB:
        return _raw.convert_TypeA_to_TypeB(src)
    elif isinstance(src, TypeA) and target_type == TypeC:
        return _raw.convert_TypeA_to_TypeC(src)
    # ... 20 个分支

# GOOD: 注册表模式
_CONVERT_REGISTRY = {}

def register_convert(src_type, dst_type, func):
    _CONVERT_REGISTRY[(src_type, dst_type)] = func

def convert(src, target_type):
    key = (type(src), target_type)
    func = _CONVERT_REGISTRY.get(key)
    if func is None:
        raise TypeError(f"No conversion from {type(src)} to {target_type}")
    return func(src)

# 注册在初始化时完成（可以自动生成）
register_convert(TypeA, TypeB, _raw.convert_TypeA_to_TypeB)
register_convert(TypeA, TypeC, _raw.convert_TypeA_to_TypeC)
# ...
```

### 3.3 Torch Integration: Zero-Copy via DLPack

```python
import torch
from torch.utils.dlpack import to_dlpack, from_dlpack

def tensor_to_ptr(t: torch.Tensor):
    """Get raw pointer + metadata from torch.Tensor for C++ consumption."""
    return t.data_ptr(), t.shape, t.stride(), t.dtype

def ptr_to_tensor(ptr, shape, dtype):
    """Wrap C++ output buffer as torch.Tensor (zero-copy)."""
    # Use torch.from_dlpack or torch.as_tensor depending on ownership
    ...
```

**dtype 映射表:**

```python
TORCH_TO_NATIVE = {
    torch.float32: NativeType.FLOAT32,
    torch.float64: NativeType.FLOAT64,
    torch.int32:   NativeType.INT32,
    torch.float16: NativeType.FLOAT16,
    # 专有类型需要特殊处理
}

NATIVE_TO_TORCH = {v: k for k, v in TORCH_TO_NATIVE.items()}
```

### 3.4 Preprocessing: Plugin Architecture

**核心问题：** 不同数据类型进计算接口前有不同的预处理，且预处理可能不在本仓库。

**设计：**

```python
class PreprocessorRegistry:
    """Pluggable preprocessing before C++ compute."""

    _registry: dict[tuple, Callable] = {}

    @classmethod
    def register(cls, dtype, op=None):
        """Decorator to register a preprocessor.

        Args:
            dtype: The data type this preprocessor handles
            op: Optional specific operation. None means all operations.
        """
        def decorator(func):
            cls._registry[(dtype, op)] = func
            return func
        return decorator

    @classmethod
    def get(cls, dtype, op):
        # Specific (dtype, op) match first, then (dtype, None) fallback
        return cls._registry.get((dtype, op)) or cls._registry.get((dtype, None))
```

**外部仓库注册预处理器：**

```python
# 在外部仓库的某个 __init__.py 或 plugin 文件中
from mylib.preprocessor import PreprocessorRegistry

@PreprocessorRegistry.register(dtype=NativeType.BFLOAT16)
def preprocess_bf16(tensor: torch.Tensor, op: str) -> torch.Tensor:
    """BF16 needs special normalization before compute."""
    return tensor / tensor.abs().max()

@PreprocessorRegistry.register(dtype=NativeType.INT8, op="mul")
def preprocess_int8_mul(tensor: torch.Tensor, op: str) -> torch.Tensor:
    """INT8 multiplication needs quantization scaling."""
    return quantize_symmetric(tensor, bits=8)
```

**Plugin 发现机制（两种方式）：**

```python
# 方式 1: Entry points（推荐，标准 Python 插件机制）
# 在外部包的 pyproject.toml 中：
# [project.entry-points."mylib.preprocessors"]
# bf16 = "external_pkg.preprocess:register_bf16"

# 方式 2: 显式注册（简单，适合公司内部）
# 在使用方代码中：
import mylib
import external_preprocessors  # 导入即注册
result = mylib.compute("add", a, b)  # 预处理自动生效
```

### 3.5 Header Parsing Strategy

头文件很长且有专业名词。解析策略：

```python
# header_parser.py 的职责：
# 1. 用正则或 libclang 解析头文件
# 2. 提取所有函数签名
# 3. 分类：conversion vs compute
# 4. 提取类型信息
# 5. 输出结构化的 function_table.json

# 分类规则（基于命名惯例）：
PATTERNS = {
    "convert": r"convert_(\w+)_to_(\w+)",       # convert_{src}_to_{dst}
    "compute": r"compute_(\w+)_(\w+)_(\w+)",    # compute_{op}_{typeA}_{typeB}
}
```

**输出的 function_table.json：**
```json
{
  "types": ["TypeA", "TypeB", "TypeC"],
  "conversions": [
    {"src": "TypeA", "dst": "TypeB", "c_func": "convert_TypeA_to_TypeB", "signature": "int(const TypeA*, TypeB*, int)"}
  ],
  "computations": [
    {"op": "add", "type_a": "TypeA", "type_b": "TypeA", "out_type": "TypeA", "c_func": "compute_add_TypeA_TypeA", "signature": "int(const TypeA*, const TypeA*, TypeA*, int)"}
  ]
}
```

---

## 4. File Structure

```
mylib/
├── __init__.py                 # Public API: compute(), convert()
├── api.py                      # Layer 0: Torch frontend
├── facade.py                   # Layer 1: Type dispatch + registry
├── preprocessor.py             # Layer 1.5: Pluggable preprocessing
├── types.py                    # Type definitions + dtype mapping
├── _raw_bindings.so            # Layer 2: Auto-generated pybind11 module
│
├── _codegen/                   # Build-time code generation
│   ├── header_parser.py        # Parse C++ headers → function_table.json
│   ├── binding_generator.py    # function_table.json → _raw_bindings.cpp
│   ├── registry_generator.py   # function_table.json → registry init code
│   └── function_table.json     # Intermediate representation (generated)
│
├── _cpp/                       # C++ source for pybind11
│   ├── _raw_bindings.cpp       # Generated pybind11 code
│   └── CMakeLists.txt          # Build configuration
│
└── setup.py / pyproject.toml   # Build: invokes codegen + compile
```

---

## 5. Build Pipeline

```
[1] Parse Headers
    header.h → header_parser.py → function_table.json

[2] Generate Binding Code
    function_table.json → binding_generator.py → _raw_bindings.cpp
    function_table.json → registry_generator.py → _registry_init.py

[3] Compile
    _raw_bindings.cpp + libfoo.so → pybind11 compile → _raw_bindings.so
    (可以用 torch.utils.cpp_extension.load() 做 JIT 编译)

[4] Package
    _raw_bindings.so + Python facade → mylib/
```

### 两种编译模式

**AOT (Ahead-of-Time) — 生产环境推荐:**
```python
# setup.py
from pybind11.setup_helpers import Pybind11Extension

ext_modules = [
    Pybind11Extension(
        "mylib._raw_bindings",
        ["mylib/_cpp/_raw_bindings.cpp"],
        libraries=["foo"],          # link libfoo.so
        library_dirs=["path/to/so"],
    ),
]
```

**JIT (Just-in-Time) — 开发调试用:**
```python
from torch.utils.cpp_extension import load

_raw = load(
    name="_raw_bindings",
    sources=["mylib/_cpp/_raw_bindings.cpp"],
    extra_ldflags=["-lfoo", "-Lpath/to/so"],
    verbose=True,
)
```

---

## 6. Output Type Inference Rules

计算接口的输出类型如何确定？

```python
# 方式 1: 跟随 C++ 函数签名（从 function_table.json 读取）
# compute_add_TypeA_TypeB → out_type = TypeB (以头文件为准)

# 方式 2: 用户显式指定
result = mylib.compute("add", a, b, out_dtype=mylib.TypeC)

# 方式 3: 类型提升规则（类似 numpy/torch）
TYPE_PROMOTION = {
    (TypeA, TypeA): TypeA,
    (TypeA, TypeB): TypeB,  # B 精度更高
    (TypeB, TypeC): TypeC,  # C 精度更高
}

def infer_output_type(dtype_a, dtype_b):
    return TYPE_PROMOTION.get((dtype_a, dtype_b), dtype_b)
```

---

## 7. Error Handling

```python
class ConversionNotSupported(TypeError):
    """No C++ function registered for this type pair."""
    def __init__(self, src_type, dst_type):
        super().__init__(
            f"Cannot convert {src_type} to {dst_type}. "
            f"Supported: {list_supported_conversions()}"
        )

class ComputeNotSupported(TypeError):
    """No C++ function registered for this op+type combination."""
    def __init__(self, op, dtype_a, dtype_b):
        super().__init__(
            f"Operation '{op}' not supported for ({dtype_a}, {dtype_b}). "
            f"Supported: {list_supported_computes(op)}"
        )
```

---

## 8. Progressive Disclosure Summary

| Layer | 用户看到什么 | 需要了解什么 |
|-------|-------------|-------------|
| **0** | `mylib.compute("add", a, b)` | 什么都不需要知道 |
| **1** | `compute("add", a, b, out_dtype=TypeC)` | 类型系统 |
| **1.5** | `PreprocessorRegistry.register(...)` | 预处理 hook |
| **2** | `_raw._compute_add_TypeA_TypeB(...)` | C++ 函数命名 |
| **3** | 修改 `_raw_bindings.cpp` | pybind11 + C++ |
