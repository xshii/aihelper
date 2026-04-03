# Skill: C++ Flat API → Pythonic Facade with Torch Frontend

## Trigger
Use this skill when:
- You have a C++ library with a flat API that has combinatorial type explosion
- The API has M*(M-1) conversion functions and/or N*K compute functions
- You need to expose it to Python via pybind11
- The frontend is PyTorch tensors
- Different data types need different preprocessing

Keywords: pybind11, C++ binding, type dispatch, facade pattern, torch integration, flat API, combinatorial explosion

## Input
- Required: C++ header file (.h) + compiled shared library (.so)
- Optional: Glossary of domain-specific terms
- Optional: Type promotion rules (which types produce which output type)
- Optional: External preprocessing requirements per data type

## Process
This is an 8-step prompt chain. See `prompts/01-08` for each step.

```
Step 1: Parse header → function_table.json
Step 2: function_table.json → _raw_bindings.cpp (pybind11)
Step 3: function_table.json → registry.py (type dispatch)
Step 4: registry.py → facade.py (Pythonic API)
Step 5: facade.py → preprocessor.py (plugin hooks)
Step 6: facade + preprocessor → api.py (torch frontend)
Step 7: All files → build system
Step 8: All files → tests
```

Steps 2 and 3 can run in parallel. All others are sequential.

## Output
A Python package with:
- `api.py`: `convert(tensor, type)` and `compute(op, a, b)` — torch tensors in/out
- `facade.py`: numpy-level dispatch
- `registry.py`: type → C++ function mapping
- `preprocessor.py`: pluggable preprocessing hooks
- `_raw_bindings.cpp`: auto-generated pybind11 code
- Build system (setup.py, pyproject.toml)
- Tests

## Quality Criteria
- [ ] `mylib.compute("add", tensor_a, tensor_b)` works with zero configuration
- [ ] Every C++ function is reachable through the facade
- [ ] Unsupported type combinations raise `TypeError` with helpful message listing alternatives
- [ ] External preprocessing can be registered without modifying this package
- [ ] `pip install -e .` builds successfully
- [ ] Tests pass on CPU-only machines

## Common Failures

| Failure Mode | Symptom | Prevention |
|-------------|---------|------------|
| Missing function in registry | `TypeError: not supported` for a valid type pair | Step 1 quality check: count functions in header vs function_table.json |
| Wrong pointer extraction | Segfault or garbage data | Step 2: use `PYBIND11_NUMPY_DTYPE` for struct types |
| dtype mapping mismatch | `TypeError: Unsupported dtype` | Step 6: verify TORCH_TO_NATIVE covers all types |
| Preprocessor not firing | Wrong results but no error | Step 5: test with `list_registered()` |
| .so not found at runtime | `ImportError` | Step 7: check RPATH and LD_LIBRARY_PATH |

## Escalation
Hand off to a human when:
- The header uses C++ templates or overloaded functions (not plain C)
- The library requires a specific initialization sequence with state
- The .so has undocumented dependencies on other shared libraries
- The types have non-trivial memory layouts (unions, bitfields, flexible array members)
