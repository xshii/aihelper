# Step 5: Add Pluggable Preprocessing

## Role
You are a Python plugin system designer. You add a hook-based preprocessing layer.

## Task
Given `facade.py` (from Step 4), create `preprocessor.py` — a pluggable preprocessing system that runs type-specific transformations on data BEFORE it enters the C++ compute functions. Then modify `facade.py` to call preprocessing automatically.

## Context
Different data types need different preprocessing before computation:
- Some types need normalization
- Some types need quantization
- Some types need format conversion
- These preprocessors may be defined in EXTERNAL packages, not in this repo

You must design a plugin architecture that allows external code to register preprocessors.

## Rules
1. DO: Use a registry pattern — external code registers preprocessors by decorating functions.
2. DO: Support two levels of specificity: `(dtype)` for all ops, and `(dtype, op)` for specific ops.
3. DO: Make registration order-independent — preprocessors can be registered at import time.
4. DO: Make preprocessing optional — if no preprocessor is registered, data passes through unchanged.
5. DO: Return the same type (numpy array) from preprocessors.
6. DON'T: Put any concrete preprocessing logic here. This file is the framework only.
7. DON'T: Make preprocessing mandatory. No preprocessor registered = data passes through unchanged.
8. NEVER: Modify the original input array. Always return a new array or a copy.

## Steps
1. Create `PreprocessorRegistry` class with `register()` decorator and `get()` lookup.
2. Create `PostprocessorRegistry` class with the same interface (for output transformation).
3. Modify `facade.py`: in `compute()`, call preprocessor before C++ and postprocessor after.
4. Document the plugin registration API for external packages.

## Output Format

File: `preprocessor.py`

```python
"""Pluggable preprocessing for type-specific data transformation.

External packages register preprocessors at import time:

    from mylib.preprocessor import PreprocessorRegistry
    from mylib.registry import NativeType

    @PreprocessorRegistry.register(NativeType.FLOAT16)
    def preprocess_fp16(data, op):
        # Runs before ANY compute op on FLOAT16 data
        return data / data.max()

    @PreprocessorRegistry.register(NativeType.INT8, op="mul")
    def preprocess_int8_mul(data, op):
        # Runs only before "mul" on INT8 data
        return quantize(data)
"""

import numpy as np
from typing import Callable, Optional
from .registry import NativeType


class PreprocessorRegistry:
    """Registry for type-specific preprocessing functions.

    Preprocessors transform data BEFORE it enters C++ compute.
    Registration is order-independent and can happen at import time.
    """

    _registry: dict[tuple[NativeType, Optional[str]], Callable] = {}

    @classmethod
    def register(cls, dtype: NativeType, op: Optional[str] = None):
        """Decorator to register a preprocessor.

        Args:
            dtype: The native type this preprocessor handles.
            op: Specific operation name. None = all operations.

        The decorated function signature must be:
            def preprocess(data: np.ndarray, op: str) -> np.ndarray
        """
        def decorator(func: Callable) -> Callable:
            cls._registry[(dtype, op)] = func
            return func
        return decorator

    @classmethod
    def get(cls, dtype: NativeType, op: str) -> Optional[Callable]:
        """Look up preprocessor. Specific (dtype, op) match wins over (dtype, None)."""
        return cls._registry.get((dtype, op)) or cls._registry.get((dtype, None))

    @classmethod
    def apply(cls, data: np.ndarray, dtype: NativeType, op: str) -> np.ndarray:
        """Apply preprocessing if registered. Pass through if not."""
        func = cls.get(dtype, op)
        if func is None:
            return data
        result = func(data, op)
        assert isinstance(result, np.ndarray), (
            f"Preprocessor for ({dtype}, {op}) must return np.ndarray, got {type(result)}"
        )
        return result

    @classmethod
    def list_registered(cls) -> list[tuple[str, Optional[str]]]:
        """List all registered (dtype, op) pairs."""
        return [(d.value, o) for d, o in cls._registry]

    @classmethod
    def clear(cls):
        """Clear all registrations. Useful for testing."""
        cls._registry.clear()


class PostprocessorRegistry:
    """Registry for type-specific postprocessing functions.

    Same API as PreprocessorRegistry, but runs AFTER C++ compute.
    """

    _registry: dict[tuple[NativeType, Optional[str]], Callable] = {}

    @classmethod
    def register(cls, dtype: NativeType, op: Optional[str] = None):
        def decorator(func: Callable) -> Callable:
            cls._registry[(dtype, op)] = func
            return func
        return decorator

    @classmethod
    def get(cls, dtype: NativeType, op: str) -> Optional[Callable]:
        return cls._registry.get((dtype, op)) or cls._registry.get((dtype, None))

    @classmethod
    def apply(cls, data: np.ndarray, dtype: NativeType, op: str) -> np.ndarray:
        func = cls.get(dtype, op)
        if func is None:
            return data
        result = func(data, op)
        assert isinstance(result, np.ndarray), (
            f"Postprocessor for ({dtype}, {op}) must return np.ndarray, got {type(result)}"
        )
        return result

    @classmethod
    def clear(cls):
        cls._registry.clear()
```

Then modify `facade.py` — add these lines to the `compute()` function:

```python
def compute(op, a, b, out_dtype=None):
    type_a = _infer_native_type(a)
    type_b = _infer_native_type(b)

    # === NEW: Preprocessing ===
    from .preprocessor import PreprocessorRegistry
    a = PreprocessorRegistry.apply(a, type_a, op)
    b = PreprocessorRegistry.apply(b, type_b, op)

    func = get_compute_func(op, type_a, type_b)
    # ... (rest unchanged) ...

    # === NEW: Postprocessing ===
    from .preprocessor import PostprocessorRegistry
    out = PostprocessorRegistry.apply(out, out_dtype, op)

    return out
```

## External Registration Example

In an external package (`external_preprocess/__init__.py`):

```python
"""Import this package to register preprocessors for mylib."""

from mylib.preprocessor import PreprocessorRegistry
from mylib.registry import NativeType
import numpy as np


@PreprocessorRegistry.register(NativeType.FLOAT16)
def preprocess_fp16(data: np.ndarray, op: str) -> np.ndarray:
    """FP16 needs normalization to avoid overflow in compute."""
    scale = np.abs(data).max()
    if scale > 0:
        return (data / scale).astype(data.dtype)
    return data


@PreprocessorRegistry.register(NativeType.INT8, op="mul")
def preprocess_int8_mul(data: np.ndarray, op: str) -> np.ndarray:
    """INT8 multiplication needs symmetric quantization."""
    return np.clip(data, -127, 127).astype(data.dtype)
```

Usage:
```python
import mylib
import external_preprocess  # Just importing registers the preprocessors

result = mylib.compute("mul", int8_array_a, int8_array_b)
# ↑ preprocess_int8_mul runs automatically before C++ compute
```

## Quality Checklist
- [ ] `PreprocessorRegistry.register()` works as a decorator
- [ ] `PreprocessorRegistry.apply()` returns data unchanged when no preprocessor is registered
- [ ] `PreprocessorRegistry.apply()` returns data unchanged when no preprocessor is registered
- [ ] Specific (dtype, op) match takes priority over generic (dtype, None)
- [ ] Preprocessors never modify the input array in-place (return new array)
- [ ] `facade.py` calls preprocessing before C++ compute and postprocessing after
- [ ] External packages can register preprocessors by simply being imported
- [ ] `clear()` method exists for testing

## Edge Cases
- If a preprocessor raises an exception: let it propagate — do NOT catch and silently skip
- If a preprocessor changes the dtype of the array: raise AssertionError — dtype must be preserved
- If both generic and specific preprocessors exist: only the specific one runs (not both)

---
[OPERATOR: Paste the facade.py from Step 4 below this line.]
