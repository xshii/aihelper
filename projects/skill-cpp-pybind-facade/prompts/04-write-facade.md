# Step 4: Registry → Pythonic Facade

## Role
You are a Python API designer. You create a clean, Pythonic interface on top of a type dispatch registry.

## Task
Given `registry.py` (from Step 3), write `facade.py` — two entry-point functions `convert()` and `compute()` that hide all the type dispatch complexity.

## Context
The registry maps `(type, type)` → C++ function. Your facade provides the user-facing API:
- `convert(data, target_type)` — one function replaces M*(M-1) conversion functions
- `compute(op, a, b)` — one function replaces N*K compute functions

Users of this facade pass numpy arrays. They never need to know which C++ function is called underneath.

## Rules
1. DO: Accept numpy arrays as input and return numpy arrays as output.
2. DO: Infer input types from the array's dtype automatically.
3. DO: Allocate the output buffer yourself — the user should not have to.
4. DO: Check return codes from C++ functions and raise on error.
5. DON'T: Import torch here. Torch integration is in a later step (api.py).
6. DON'T: Add preprocessing logic. That's the preprocessor's job (Step 5).
7. NEVER: Expose the registry internals. Users see `convert()` and `compute()`, nothing else.

## Steps
1. Import `registry.py` and its `NativeType` enum.
2. Build a `NUMPY_DTYPE_TO_NATIVE` mapping: `{np.dtype(...): NativeType.X}`.
3. Build a `NATIVE_TO_NUMPY_DTYPE` reverse mapping.
4. Implement `convert(src: np.ndarray, target_type: NativeType) -> np.ndarray`:
   - Infer src_type from src.dtype
   - Look up the conversion function
   - Allocate output array
   - Call the C++ function
   - Return the output
5. Implement `compute(op: str, a: np.ndarray, b: np.ndarray, out_dtype: NativeType = None) -> np.ndarray`:
   - Infer type_a, type_b from input dtypes
   - Look up the compute function
   - Determine output type (from registry or explicit `out_dtype`)
   - Allocate output array
   - Call the C++ function
   - Return the output

## Output Format

File: `facade.py`

```python
"""Pythonic facade over the C++ flat API.

Usage:
    from mylib.facade import convert, compute

    result = convert(my_array, NativeType.COMPLEX128)
    result = compute("add", array_a, array_b)
"""

import numpy as np
from .registry import (
    NativeType,
    get_convert_func,
    get_compute_func,
    get_compute_output_type,
)


# === dtype mapping ===

NUMPY_TO_NATIVE: dict[np.dtype, NativeType] = {
    np.dtype("complex64"):  NativeType.COMPLEX64,
    np.dtype("complex128"): NativeType.COMPLEX128,
    np.dtype("float32"):    NativeType.FLOAT32,
    # ... for custom struct types, register numpy structured dtypes
}

NATIVE_TO_NUMPY: dict[NativeType, np.dtype] = {v: k for k, v in NUMPY_TO_NATIVE.items()}


def _infer_native_type(arr: np.ndarray) -> NativeType:
    """Infer NativeType from a numpy array's dtype."""
    native = NUMPY_TO_NATIVE.get(arr.dtype)
    if native is None:
        raise TypeError(
            f"Unsupported dtype {arr.dtype}. "
            f"Supported: {[str(k) for k in NUMPY_TO_NATIVE]}"
        )
    return native


def convert(src: np.ndarray, target_type: NativeType) -> np.ndarray:
    """Convert array from one native type to another.

    Args:
        src: Input array.
        target_type: Target NativeType.

    Returns:
        New array of the target type.
    """
    src_type = _infer_native_type(src)
    if src_type == target_type:
        return src.copy()

    func = get_convert_func(src_type, target_type)
    dst_dtype = NATIVE_TO_NUMPY[target_type]
    dst = np.empty(src.shape, dtype=dst_dtype)

    ret = func(src, dst)
    if ret != 0:
        raise RuntimeError(f"C++ convert failed with code {ret}")
    return dst


def compute(
    op: str,
    a: np.ndarray,
    b: np.ndarray,
    out_dtype: NativeType = None,
) -> np.ndarray:
    """Perform a compute operation on two arrays.

    Args:
        op: Operation name ("add", "mul", etc.).
        a: First input array.
        b: Second input array.
        out_dtype: Explicit output type. If None, inferred from registry.

    Returns:
        Result array.
    """
    type_a = _infer_native_type(a)
    type_b = _infer_native_type(b)

    func = get_compute_func(op, type_a, type_b)

    if out_dtype is None:
        out_dtype = get_compute_output_type(op, type_a, type_b)

    result_np_dtype = NATIVE_TO_NUMPY[out_dtype]
    out = np.empty(a.shape, dtype=result_np_dtype)

    ret = func(a, b, out)
    if ret != 0:
        raise RuntimeError(f"C++ compute '{op}' failed with code {ret}")
    return out
```

## Quality Checklist
- [ ] `convert()` works: correct type inference, buffer allocation, function dispatch
- [ ] `compute()` works: correct type inference, output type determination, function dispatch
- [ ] Both functions handle the C++ return code (non-zero = error)
- [ ] Both functions have clear docstrings
- [ ] `_infer_native_type` gives a helpful error message listing supported types
- [ ] No import of torch (that's api.py's job)
- [ ] No preprocessing logic (that's preprocessor.py's job)
- [ ] Output arrays are properly allocated with correct shape and dtype

## Edge Cases
- If `src_type == target_type` in convert: return a copy, don't call C++
- If `a.shape != b.shape` in compute: raise ValueError before calling C++
- If a custom struct dtype doesn't map to a numpy scalar dtype: use numpy structured arrays (`np.dtype([('re', 'f4'), ('im', 'f4')])`)

---
[OPERATOR: Paste the registry.py from Step 3 below this line, and note any custom struct-to-numpy dtype mappings.]
