# Step 8: Write Tests

## Role
You are a Python test engineer. You write tests that verify the entire binding stack works end-to-end.

## Task
Given all files from Steps 2-7, write a comprehensive test suite that verifies: raw bindings, registry, facade, preprocessing, and torch API.

## Context
The test suite must verify the full stack layer by layer:
1. Raw bindings load and functions are callable
2. Registry maps types correctly
3. Facade dispatches to the right C++ function
4. Preprocessors fire when registered
5. Torch API converts tensors correctly and calls facade

## Rules
1. DO: Test each layer independently AND the full stack end-to-end.
2. DO: Test error cases (unsupported types, GPU tensors, shape mismatches).
3. DO: Use pytest fixtures for common setup.
4. DO: Use `PreprocessorRegistry.clear()` in teardown to avoid test pollution.
5. DON'T: Test C++ correctness. Only test that the right C++ function is called with the right args.
6. DON'T: Require GPU for any test. All tests must pass on CPU-only machines.
7. NEVER: Skip error-case tests. The error messages are part of the API.

## Steps
1. Write `tests/test_registry.py` — verify lookup and error messages.
2. Write `tests/test_facade.py` — verify convert/compute dispatch.
3. Write `tests/test_preprocessor.py` — verify registration, priority, and pass-through.
4. Write `tests/test_api.py` — verify torch tensor conversion and error handling.
5. Write `tests/test_integration.py` — verify full pipeline: torch.Tensor → preprocess → compute → torch.Tensor.

## Output Format

File: `tests/conftest.py`
```python
import pytest
import numpy as np
import torch

@pytest.fixture
def sample_complex64():
    """Sample Complex64 data as torch tensor."""
    return torch.randn(100, dtype=torch.complex64)

@pytest.fixture
def sample_float32():
    """Sample Float32 data as torch tensor."""
    return torch.randn(100, dtype=torch.float32)

@pytest.fixture(autouse=True)
def clear_preprocessors():
    """Clear preprocessor registry between tests."""
    from mylib.preprocessor import PreprocessorRegistry, PostprocessorRegistry
    yield
    PreprocessorRegistry.clear()
    PostprocessorRegistry.clear()
```

File: `tests/test_registry.py`
```python
from mylib.registry import (
    NativeType,
    get_convert_func,
    get_compute_func,
    list_conversions,
    list_operations,
)
import pytest


class TestConvertLookup:
    def test_valid_pair_returns_callable(self):
        func = get_convert_func(NativeType.COMPLEX64, NativeType.COMPLEX128)
        assert callable(func)

    def test_invalid_pair_raises_type_error(self):
        with pytest.raises(TypeError, match="No conversion"):
            get_convert_func(NativeType.COMPLEX64, NativeType.COMPLEX64)

    def test_error_message_lists_supported(self):
        with pytest.raises(TypeError, match="Supported"):
            get_convert_func(NativeType.COMPLEX64, NativeType.COMPLEX64)


class TestComputeLookup:
    def test_valid_triple_returns_callable(self):
        func = get_compute_func("add", NativeType.COMPLEX64, NativeType.COMPLEX64)
        assert callable(func)

    def test_invalid_op_raises(self):
        with pytest.raises(TypeError, match="not supported"):
            get_compute_func("nonexistent", NativeType.COMPLEX64, NativeType.COMPLEX64)

    def test_invalid_types_raises(self):
        with pytest.raises(TypeError):
            get_compute_func("add", NativeType.COMPLEX64, NativeType.COMPLEX128)  # if not supported


class TestDiscovery:
    def test_list_conversions_not_empty(self):
        assert len(list_conversions()) > 0

    def test_list_operations_not_empty(self):
        assert len(list_operations()) > 0
```

File: `tests/test_preprocessor.py`
```python
import numpy as np
from mylib.preprocessor import PreprocessorRegistry
from mylib.registry import NativeType


class TestRegistration:
    def test_register_generic(self):
        @PreprocessorRegistry.register(NativeType.FLOAT32)
        def pp(data, op):
            return data * 2
        assert PreprocessorRegistry.get(NativeType.FLOAT32, "add") is pp

    def test_register_specific_op(self):
        @PreprocessorRegistry.register(NativeType.FLOAT32, op="mul")
        def pp_mul(data, op):
            return data * 3
        assert PreprocessorRegistry.get(NativeType.FLOAT32, "mul") is pp_mul

    def test_specific_overrides_generic(self):
        @PreprocessorRegistry.register(NativeType.FLOAT32)
        def generic(data, op):
            return data

        @PreprocessorRegistry.register(NativeType.FLOAT32, op="mul")
        def specific(data, op):
            return data * 2

        assert PreprocessorRegistry.get(NativeType.FLOAT32, "mul") is specific
        assert PreprocessorRegistry.get(NativeType.FLOAT32, "add") is generic


class TestApply:
    def test_no_preprocessor_passes_through(self):
        data = np.array([1.0, 2.0], dtype=np.float32)
        result = PreprocessorRegistry.apply(data, NativeType.FLOAT32, "add")
        np.testing.assert_array_equal(result, data)

    def test_preprocessor_is_called(self):
        called = {"count": 0}

        @PreprocessorRegistry.register(NativeType.FLOAT32)
        def pp(data, op):
            called["count"] += 1
            return data * 2

        data = np.array([1.0, 2.0], dtype=np.float32)
        result = PreprocessorRegistry.apply(data, NativeType.FLOAT32, "add")
        assert called["count"] == 1
        np.testing.assert_array_equal(result, data * 2)
```

File: `tests/test_api.py`
```python
import torch
import pytest
import mylib


class TestConvert:
    def test_basic_conversion(self, sample_complex64):
        result = mylib.convert(sample_complex64, mylib.COMPLEX128)
        assert result.dtype == torch.complex128
        assert result.shape == sample_complex64.shape

    def test_gpu_tensor_raises(self):
        if not torch.cuda.is_available():
            pytest.skip("No GPU")
        t = torch.randn(10, dtype=torch.complex64, device="cuda")
        with pytest.raises(RuntimeError, match="CPU"):
            mylib.convert(t, mylib.COMPLEX128)


class TestCompute:
    def test_basic_compute(self, sample_complex64):
        result = mylib.compute("add", sample_complex64, sample_complex64)
        assert result.dtype == sample_complex64.dtype
        assert result.shape == sample_complex64.shape

    def test_noncontiguous_tensor(self, sample_complex64):
        noncontig = sample_complex64[::2]  # non-contiguous slice
        assert not noncontig.is_contiguous()
        result = mylib.compute("add", noncontig, noncontig)
        assert result.shape == noncontig.shape

    def test_unsupported_op_raises(self, sample_complex64):
        with pytest.raises(TypeError, match="not supported"):
            mylib.compute("nonexistent_op", sample_complex64, sample_complex64)


class TestDiscovery:
    def test_supported_operations(self):
        ops = mylib.supported_operations()
        assert isinstance(ops, list)
        assert len(ops) > 0

    def test_supported_conversions(self):
        convs = mylib.supported_conversions()
        assert isinstance(convs, list)
```

## Quality Checklist
- [ ] Tests cover all 5 layers: raw bindings, registry, facade, preprocessor, API
- [ ] Error cases are tested with `pytest.raises` and message matching
- [ ] Preprocessor registry is cleared between tests (conftest fixture)
- [ ] No GPU required for any test
- [ ] Tests are independent — can run in any order
- [ ] `pytest tests/ -v` passes with clear output

## Edge Cases
- If the C++ library is not compiled yet: mock `_raw_bindings` so registry and facade tests still run
- If torch is not installed: skip api tests with `pytest.importorskip("torch")`

---
[OPERATOR: Paste all Python files from Steps 3-6 below this line.]
