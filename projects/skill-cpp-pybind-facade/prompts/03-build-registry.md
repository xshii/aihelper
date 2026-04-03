# Step 3: Function Table → Python Type Registry

## Role
You are a Python code generator. You build a dispatch registry that maps type combinations to C++ functions.

## Task
Given a `function_table.json`, generate a `registry.py` that creates lookup tables for type-based dispatch.

## Context
The raw C++ bindings (from Step 2) expose hundreds of flat functions like `_raw.convert_TypeA_to_TypeB()`. The registry maps `(src_type, dst_type)` → the right function, so a higher-level facade (Step 4) can dispatch with a single `convert(src, dst_type)` call.

## Rules
1. DO: Register EVERY conversion and computation from the function table.
2. DO: Use tuple keys `(type1, type2)` for lookups — simple and fast.
3. DO: Generate the registration code mechanically — one line per function.
4. DO: Add a `list_supported()` function for discoverability.
5. DON'T: Add any logic beyond registration and lookup.
6. DON'T: Import `_raw_bindings` at module level. Use lazy import so the module works even before compilation.
7. NEVER: Hardcode type names as strings in the lookup. Use an enum or constants.

## Steps
1. Read the function_table.json.
2. Generate a `NativeType` enum from the `types` array.
3. Generate a `CONVERT_REGISTRY` dict: `{(NativeType.X, NativeType.Y): "_raw.convert_X_to_Y"}`.
4. Generate a `COMPUTE_REGISTRY` dict: `{("op", NativeType.X, NativeType.Y): "_raw.compute_op_X_Y"}`.
5. Generate lookup functions: `get_convert_func(src, dst)` and `get_compute_func(op, type_a, type_b)`.
6. Generate discovery functions: `list_conversions()`, `list_computations(op=None)`.

## Output Format

File: `registry.py`

```python
"""Type dispatch registry. Auto-generated from function_table.json."""

from enum import Enum
from typing import Callable, Optional


class NativeType(Enum):
    """All native types from the C++ library."""
    COMPLEX64 = "Complex64"
    COMPLEX128 = "Complex128"
    FLOAT32 = "Float32"
    # ... one entry per type


def _get_raw():
    """Lazy import of raw bindings module."""
    import _raw_bindings as _raw
    return _raw


# === Conversion Registry ===

_CONVERT_REGISTRY: dict[tuple[NativeType, NativeType], str] = {
    (NativeType.COMPLEX64, NativeType.COMPLEX128): "convert_Complex64_to_Complex128",
    (NativeType.COMPLEX128, NativeType.COMPLEX64): "convert_Complex128_to_Complex64",
    # ... one entry per conversion function
}


def get_convert_func(src_type: NativeType, dst_type: NativeType) -> Callable:
    """Look up the conversion function for a type pair."""
    key = (src_type, dst_type)
    func_name = _CONVERT_REGISTRY.get(key)
    if func_name is None:
        supported = [(s.value, d.value) for s, d in _CONVERT_REGISTRY]
        raise TypeError(
            f"No conversion from {src_type.value} to {dst_type.value}. "
            f"Supported: {supported}"
        )
    return getattr(_get_raw(), func_name)


# === Compute Registry ===

_COMPUTE_REGISTRY: dict[tuple[str, NativeType, NativeType], str] = {
    ("add", NativeType.COMPLEX64, NativeType.COMPLEX64): "compute_add_Complex64_Complex64",
    ("mul", NativeType.COMPLEX64, NativeType.COMPLEX128): "compute_mul_Complex64_Complex128",
    # ... one entry per compute function
}

# Output type mapping: which type does each compute produce?
_COMPUTE_OUTPUT_TYPE: dict[tuple[str, NativeType, NativeType], NativeType] = {
    ("add", NativeType.COMPLEX64, NativeType.COMPLEX64): NativeType.COMPLEX64,
    ("mul", NativeType.COMPLEX64, NativeType.COMPLEX128): NativeType.COMPLEX128,
    # ... one entry per compute function
}


def get_compute_func(op: str, type_a: NativeType, type_b: NativeType) -> Callable:
    """Look up the compute function for an operation + type pair."""
    key = (op, type_a, type_b)
    func_name = _COMPUTE_REGISTRY.get(key)
    if func_name is None:
        supported = [(o, a.value, b.value) for o, a, b in _COMPUTE_REGISTRY if o == op]
        raise TypeError(
            f"Operation '{op}' not supported for ({type_a.value}, {type_b.value}). "
            f"Supported type pairs for '{op}': {supported}"
        )
    return getattr(_get_raw(), func_name)


def get_compute_output_type(op: str, type_a: NativeType, type_b: NativeType) -> NativeType:
    """Get the output type for a compute operation."""
    return _COMPUTE_OUTPUT_TYPE[(op, type_a, type_b)]


# === Discovery ===

def list_conversions() -> list[tuple[str, str]]:
    """List all supported (src, dst) conversion pairs."""
    return [(s.value, d.value) for s, d in _CONVERT_REGISTRY]

def list_computations(op: Optional[str] = None) -> list[tuple[str, str, str]]:
    """List all supported (op, type_a, type_b) compute triples."""
    entries = _COMPUTE_REGISTRY.keys()
    if op:
        entries = [(o, a, b) for o, a, b in entries if o == op]
    return [(o, a.value, b.value) for o, a, b in entries]

def list_operations() -> list[str]:
    """List all supported operation names."""
    return sorted(set(op for op, _, _ in _COMPUTE_REGISTRY))
```

## Quality Checklist
- [ ] Every conversion in function_table.json has an entry in `_CONVERT_REGISTRY`
- [ ] Every computation in function_table.json has an entry in `_COMPUTE_REGISTRY` AND `_COMPUTE_OUTPUT_TYPE`
- [ ] `NativeType` enum covers every type in function_table.json
- [ ] Lookup functions raise `TypeError` with helpful messages listing supported options
- [ ] No import of `_raw_bindings` at module level (lazy import only)
- [ ] `list_*` functions return human-readable strings, not enum objects

## Edge Cases
- If two functions have the same type pair but different parameter signatures: raise this to the operator, do not guess
- If a type name contains special characters or is a C keyword: use a sanitized enum name with `_ORIGINAL_NAME` mapping

---
[OPERATOR: Paste the function_table.json from Step 1 below this line.]
