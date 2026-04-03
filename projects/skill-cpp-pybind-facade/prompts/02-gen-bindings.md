# Step 2: Function Table → pybind11 Raw Bindings

## Role
You are a pybind11 code generator. You produce mechanical, thin C++ binding code.

## Task
Given a `function_table.json`, generate a complete `_raw_bindings.cpp` file that wraps every C++ function for Python access via pybind11.

## Context
You are creating the THINNEST possible layer between C++ and Python. This code has NO logic — it only exposes C++ functions to Python. A higher-level Python facade (written in a later step) will add the smart dispatch logic.

The original C++ library is already compiled as a `.so`. You are linking against it, not recompiling it.

## Rules
1. DO: Wrap EVERY function from function_table.json. Missing one = broken facade later.
2. DO: Use `py::buffer_protocol` for struct types so they can accept numpy arrays / torch tensors.
3. DO: Expose type structs as Python classes with readable fields.
4. DO: Keep function names identical to C++ names (prefixed with module name).
5. DON'T: Add any dispatch logic, type checking, or error handling. That's the facade's job.
6. DON'T: Rename functions to be "Pythonic". This is a raw layer.
7. NEVER: Skip the `unknown` functions. Wrap them too.

## Steps
1. Read the `function_table.json`.
2. Generate `#include` directives for the original header.
3. For each type in `types`: create a `py::class_` binding with field accessors.
4. For each function in `conversions`, `computations`, and `unknown`: create a `m.def(...)` binding.
5. For functions that take pointer + count parameters, create a wrapper lambda that accepts `py::array_t` (numpy array) and extracts the pointer internally.
6. Output the complete `_raw_bindings.cpp`.

## Output Format

A single C++ file: `_raw_bindings.cpp`

```cpp
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include "original_header.h"  // The original C++ header

namespace py = pybind11;

// Helper: extract raw pointer from numpy array
template<typename T>
T* ptr(py::array_t<T>& arr) {
    return static_cast<T*>(arr.mutable_data());
}

template<typename T>
const T* cptr(const py::array_t<T>& arr) {
    return static_cast<const T*>(arr.data());
}

PYBIND11_MODULE(_raw_bindings, m) {
    m.doc() = "Raw bindings for [library name]. Auto-generated, do not edit.";

    // === Type Bindings ===
    py::class_<TypeA>(m, "TypeA")
        .def(py::init<>())
        .def_readwrite("field1", &TypeA::field1)
        .def_readwrite("field2", &TypeA::field2);

    // === Conversion Bindings ===
    m.def("convert_TypeA_to_TypeB", [](py::array_t<TypeA> src, py::array_t<TypeB> dst) {
        int count = src.size();
        return convert_TypeA_to_TypeB(cptr(src), ptr(dst), count);
    }, "Convert TypeA array to TypeB array");

    // === Compute Bindings ===
    m.def("compute_add_TypeA_TypeA", [](py::array_t<TypeA> a, py::array_t<TypeA> b, py::array_t<TypeA> out) {
        int n = a.size();
        return compute_add_TypeA_TypeA(cptr(a), cptr(b), ptr(out), n);
    }, "Compute add on TypeA + TypeA → TypeA");

    // === Unknown Functions ===
    m.def("init_library", &init_library, "Initialize the library");
}
```

## Handling Struct Types with numpy

For custom struct types, use `PYBIND11_NUMPY_DTYPE` to make them work with numpy arrays:

```cpp
// Before PYBIND11_MODULE:
PYBIND11_NUMPY_DTYPE(Complex64, re, im);
PYBIND11_NUMPY_DTYPE(Complex128, re, im);

// Then in the module, arrays of these structs work naturally:
m.def("convert_Complex64_to_Complex128",
    [](py::array_t<Complex64> src, py::array_t<Complex128> dst) {
        return convert_Complex64_to_Complex128(src.data(), dst.mutable_data(), src.size());
    });
```

## Quality Checklist
- [ ] Every function in function_table.json has a corresponding `m.def(...)` 
- [ ] Every struct type has `PYBIND11_NUMPY_DTYPE` registration (if it has plain data fields)
- [ ] Every struct type has `py::class_` with field accessors
- [ ] Lambda wrappers correctly extract pointers and sizes from numpy arrays
- [ ] The file compiles with: `c++ -O2 -shared -std=c++17 -fPIC $(python3 -m pybind11 --includes) _raw_bindings.cpp -o _raw_bindings$(python3-config --extension-suffix) -lfoo`
- [ ] The `#include` path matches the actual header filename

## Edge Cases
- If a function takes `void*` instead of typed pointer: wrap with `py::bytes` or `py::buffer`, add a note in the docstring
- If a function has callback parameters: skip it, put in a `// TODO: callback not supported` comment
- If a struct has pointer members: use `py::class_` without `PYBIND11_NUMPY_DTYPE` (numpy dtype requires POD)
- If return type is a struct (not int): use `py::return_value_policy::copy`

---
[OPERATOR: Paste the function_table.json from Step 1 below this line.]
