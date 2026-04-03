# Step 6: Facade → Torch Tensor Frontend

## Role
You are a PyTorch integration engineer. You bridge numpy-based facades to the torch.Tensor world.

## Task
Given `facade.py` and `preprocessor.py`, create `api.py` — the top-level user API where everything is `torch.Tensor` in, `torch.Tensor` out.

## Context
The facade works with numpy arrays. PyTorch users work with `torch.Tensor`. This layer:
1. Converts torch.Tensor → numpy for the facade
2. Calls facade
3. Converts numpy result back to torch.Tensor
4. Handles device placement (CPU only; GPU tensors must be moved first)
5. Maps `torch.dtype` to `NativeType`

## Rules
1. DO: Accept `torch.Tensor` as input and return `torch.Tensor` as output.
2. DO: Preserve the input tensor's device and requires_grad if applicable.
3. DO: Raise clear error if input is on GPU — this C++ library only supports CPU.
4. DO: Use `torch.from_numpy()` for zero-copy numpy→torch (when possible).
5. DO: Use `.numpy()` for zero-copy torch→numpy (contiguous CPU tensors).
6. DON'T: Add preprocessing logic. That's already handled by preprocessor.py via facade.py.
7. DON'T: Duplicate type dispatch logic. Call facade.convert() and facade.compute().
8. NEVER: Silently move GPU tensors to CPU. Raise an error so the user knows.

## Steps
1. Define `TORCH_TO_NATIVE` dtype mapping.
2. Implement `_ensure_cpu_contiguous(t)` helper.
3. Implement `convert(src: torch.Tensor, target_type) -> torch.Tensor`.
4. Implement `compute(op: str, a: torch.Tensor, b: torch.Tensor) -> torch.Tensor`.
5. Implement `__init__.py` that exports the public API.

## Output Format

File: `api.py`

```python
"""Top-level API. Torch tensors in, torch tensors out.

Usage:
    import mylib

    a = torch.randn(100, dtype=torch.complex64)
    b = torch.randn(100, dtype=torch.complex64)
    result = mylib.compute("add", a, b)
    converted = mylib.convert(a, mylib.Complex128)
"""

import torch
import numpy as np
from .registry import NativeType
from . import facade


# === Torch dtype ↔ NativeType mapping ===

TORCH_TO_NATIVE: dict[torch.dtype, NativeType] = {
    torch.complex64:  NativeType.COMPLEX64,
    torch.complex128: NativeType.COMPLEX128,
    torch.float32:    NativeType.FLOAT32,
    # ... map every torch dtype that corresponds to a NativeType
    # For custom struct types that have no torch.dtype equivalent,
    # users must use NativeType directly (see "Custom Types" below)
}

NATIVE_TO_TORCH: dict[NativeType, torch.dtype] = {v: k for k, v in TORCH_TO_NATIVE.items()}


def _ensure_cpu_contiguous(t: torch.Tensor) -> torch.Tensor:
    """Ensure tensor is on CPU and contiguous. Raise if on GPU."""
    if t.device.type != "cpu":
        raise RuntimeError(
            f"Tensor is on {t.device}. This library only supports CPU tensors. "
            f"Move to CPU first: tensor.cpu()"
        )
    if not t.is_contiguous():
        t = t.contiguous()
    return t


def _to_native_type(dtype_or_native) -> NativeType:
    """Accept torch.dtype or NativeType, return NativeType."""
    if isinstance(dtype_or_native, NativeType):
        return dtype_or_native
    if isinstance(dtype_or_native, torch.dtype):
        native = TORCH_TO_NATIVE.get(dtype_or_native)
        if native is None:
            raise TypeError(f"No NativeType mapping for torch.dtype {dtype_or_native}")
        return native
    raise TypeError(f"Expected torch.dtype or NativeType, got {type(dtype_or_native)}")


def convert(src: torch.Tensor, target_type) -> torch.Tensor:
    """Convert tensor to a different native type.

    Args:
        src: Input tensor (CPU, contiguous).
        target_type: Target type. Can be torch.dtype or NativeType.

    Returns:
        New tensor of the target type.
    """
    src = _ensure_cpu_contiguous(src)
    target_native = _to_native_type(target_type)

    src_np = src.numpy()
    result_np = facade.convert(src_np, target_native)

    target_torch_dtype = NATIVE_TO_TORCH.get(target_native)
    if target_torch_dtype is not None:
        return torch.from_numpy(result_np)
    else:
        # Custom struct type: return as tensor of bytes or structured array
        return torch.from_numpy(result_np.view(np.uint8))


def compute(
    op: str,
    a: torch.Tensor,
    b: torch.Tensor,
    out_dtype=None,
) -> torch.Tensor:
    """Perform a compute operation on two tensors.

    Args:
        op: Operation name ("add", "mul", etc.).
        a: First input tensor (CPU, contiguous).
        b: Second input tensor (CPU, contiguous).
        out_dtype: Explicit output type. If None, inferred.

    Returns:
        Result tensor.
    """
    a = _ensure_cpu_contiguous(a)
    b = _ensure_cpu_contiguous(b)

    out_native = _to_native_type(out_dtype) if out_dtype is not None else None

    a_np = a.numpy()
    b_np = b.numpy()
    result_np = facade.compute(op, a_np, b_np, out_dtype=out_native)

    return torch.from_numpy(result_np)


# === Discovery ===

def supported_conversions():
    """List all supported conversion pairs."""
    from .registry import list_conversions
    return list_conversions()

def supported_operations():
    """List all supported compute operations."""
    from .registry import list_operations
    return list_operations()

def supported_types_for(op: str):
    """List supported type pairs for a given operation."""
    from .registry import list_computations
    return list_computations(op=op)
```

File: `__init__.py`

```python
"""mylib — Pythonic interface to the C++ compute library.

Usage:
    import mylib
    result = mylib.compute("add", tensor_a, tensor_b)
    converted = mylib.convert(tensor_a, mylib.Complex128)
"""

from .api import convert, compute
from .api import supported_conversions, supported_operations, supported_types_for
from .registry import NativeType

# Re-export NativeType members for convenience
# so users can write mylib.COMPLEX64 instead of mylib.NativeType.COMPLEX64
for _member in NativeType:
    globals()[_member.name] = _member

__all__ = [
    "convert",
    "compute",
    "supported_conversions",
    "supported_operations",
    "supported_types_for",
    "NativeType",
] + [m.name for m in NativeType]
```

## Custom Struct Types (no torch.dtype equivalent)

For C++ struct types like `Complex64` that map to `torch.complex64`, the mapping is straightforward. But if the C++ library has custom types with no torch equivalent:

```python
# Option A: User creates tensor from raw bytes
data = torch.frombuffer(raw_bytes, dtype=torch.uint8)
result = mylib.compute("transform", data, data, out_dtype=mylib.CUSTOM_TYPE)

# Option B: Provide a helper to create "typed views"
custom_array = mylib.wrap_as(raw_pointer, shape, mylib.CUSTOM_TYPE)
```

## Quality Checklist
- [ ] `convert()` and `compute()` accept torch.Tensor, return torch.Tensor
- [ ] GPU tensors raise RuntimeError with clear message
- [ ] Non-contiguous tensors are made contiguous automatically
- [ ] dtype mapping covers all types in the registry
- [ ] `__init__.py` exports a clean public API
- [ ] No preprocessing logic (handled by facade.py → preprocessor.py)
- [ ] Discovery functions (`supported_*`) work and return readable output
- [ ] Zero-copy where possible (`.numpy()` and `torch.from_numpy()`)

## Edge Cases
- If input tensor requires_grad: call `.detach().numpy()` to avoid autograd errors
- If torch.from_numpy fails due to unsupported dtype: fall back to `torch.tensor(result_np)`
- If the C++ library modifies data in-place: clone input before passing to avoid corrupting user's tensor

---
[OPERATOR: Paste facade.py and preprocessor.py from Steps 4-5. Also note any custom types that have no torch.dtype equivalent.]
