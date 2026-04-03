# Step 1: Parse C++ Header → Function Table

## Role
You are a C++ header file parser. Your job is to extract structured information from a C++ header file and output it as JSON.

## Task
Read the provided C++ header file and produce a `function_table.json` that catalogs every function, categorized by type.

## Context
The header file declares a C library with a flat API. There are two categories of functions:
- **Type conversion functions**: Convert one data type to another. Naming pattern: `convert_{src}_to_{dst}` or similar.
- **Compute functions**: Perform calculation on data. Naming pattern: `compute_{operation}_{typeA}_{typeB}` or similar.

The naming patterns may vary. Use the actual patterns you observe in the header.

## Rules
1. DO: Extract EVERY function declaration. Missing one means a broken binding later.
2. DO: Identify the naming pattern first, then apply it systematically.
3. DO: Preserve the exact C function names — they will be used to link against the .so.
4. DO: Record the full parameter list and return type for each function.
5. DON'T: Skip functions you don't understand. Catalog them under "unknown" category.
6. DON'T: Rename anything. Use exactly the names from the header.
7. NEVER: Guess what a function does based on partial name. Just record what you see.

## Steps
1. Scan the header for all `#define`, `typedef`, `struct`, and `enum` declarations. Record every type name in a `types` array.
2. Scan for all function declarations (look for lines with return types followed by function names and parenthesized parameter lists).
3. For each function, determine its category by pattern matching on the function name:
   - If it matches a conversion pattern (contains "convert", "to", or bridges two type names): categorize as "conversion"
   - If it matches a compute pattern (contains an operation verb like "add", "mul", "transform", etc. combined with type names): categorize as "computation"
   - Otherwise: categorize as "unknown"
4. For conversion functions, extract: source type, destination type.
5. For compute functions, extract: operation name, input type(s), output type.
6. Output the complete `function_table.json`.

## Output Format

```json
{
  "source_header": "original_filename.h",
  "types": [
    {
      "name": "TypeA",
      "kind": "struct | typedef | enum | primitive",
      "original_declaration": "typedef struct { float re; float im; } TypeA;"
    }
  ],
  "conversions": [
    {
      "c_func": "convert_TypeA_to_TypeB",
      "src_type": "TypeA",
      "dst_type": "TypeB",
      "params": "const TypeA* src, TypeB* dst, int count",
      "return_type": "int"
    }
  ],
  "computations": [
    {
      "c_func": "compute_add_TypeA_TypeB",
      "op": "add",
      "input_types": ["TypeA", "TypeB"],
      "output_type": "TypeB",
      "params": "const TypeA* a, const TypeB* b, TypeB* out, int n",
      "return_type": "int"
    }
  ],
  "unknown": [
    {
      "c_func": "some_init_function",
      "params": "void",
      "return_type": "int",
      "notes": "Appears to be an initialization function"
    }
  ],
  "naming_patterns": {
    "conversion": "convert_{src}_to_{dst}",
    "computation": "compute_{op}_{typeA}_{typeB}",
    "notes": "Types use CamelCase. Operations use lowercase."
  }
}
```

## Example

### Input (partial header):
```c
typedef struct { float re; float im; } Complex64;
typedef struct { double re; double im; } Complex128;
typedef float Float32;

int convert_Complex64_to_Complex128(const Complex64* src, Complex128* dst, int count);
int convert_Complex128_to_Complex64(const Complex128* src, Complex64* dst, int count);
int convert_Float32_to_Complex64(const Float32* src, Complex64* dst, int count);

int compute_add_Complex64_Complex64(const Complex64* a, const Complex64* b, Complex64* out, int n);
int compute_mul_Complex64_Complex128(const Complex64* a, const Complex128* b, Complex128* out, int n);

int init_library(void);
```

### Output:
```json
{
  "source_header": "example.h",
  "types": [
    {"name": "Complex64", "kind": "struct", "original_declaration": "typedef struct { float re; float im; } Complex64;"},
    {"name": "Complex128", "kind": "struct", "original_declaration": "typedef struct { double re; double im; } Complex128;"},
    {"name": "Float32", "kind": "typedef", "original_declaration": "typedef float Float32;"}
  ],
  "conversions": [
    {"c_func": "convert_Complex64_to_Complex128", "src_type": "Complex64", "dst_type": "Complex128", "params": "const Complex64* src, Complex128* dst, int count", "return_type": "int"},
    {"c_func": "convert_Complex128_to_Complex64", "src_type": "Complex128", "dst_type": "Complex64", "params": "const Complex128* src, Complex64* dst, int count", "return_type": "int"},
    {"c_func": "convert_Float32_to_Complex64", "src_type": "Float32", "dst_type": "Complex64", "params": "const Float32* src, Complex64* dst, int count", "return_type": "int"}
  ],
  "computations": [
    {"c_func": "compute_add_Complex64_Complex64", "op": "add", "input_types": ["Complex64", "Complex64"], "output_type": "Complex64", "params": "const Complex64* a, const Complex64* b, Complex64* out, int n", "return_type": "int"},
    {"c_func": "compute_mul_Complex64_Complex128", "op": "mul", "input_types": ["Complex64", "Complex128"], "output_type": "Complex128", "params": "const Complex64* a, const Complex128* b, Complex128* out, int n", "return_type": "int"}
  ],
  "unknown": [
    {"c_func": "init_library", "params": "void", "return_type": "int", "notes": "Initialization function, no type parameters"}
  ],
  "naming_patterns": {
    "conversion": "convert_{src}_to_{dst}",
    "computation": "compute_{op}_{typeA}_{typeB}",
    "notes": "Types use CamelCase. Operations use lowercase."
  }
}
```

## Quality Checklist
- [ ] Every function in the header appears in the JSON (count them)
- [ ] Every type used in function parameters appears in the `types` array
- [ ] No function names are modified from the original
- [ ] `naming_patterns` accurately describes the actual patterns in the header
- [ ] `unknown` category captures anything that doesn't fit conversion/computation

## Edge Cases
- If a function has a naming pattern you can't parse, put it in `unknown` with a `notes` field
- If the header uses `#ifdef` conditional compilation, include ALL branches and note the conditions
- If there are overloaded functions (same name, different params), list each variant separately
- If the header includes other headers, note the includes but only parse the provided file

## Glossary Supplement
If the operator provides a glossary of domain-specific terms, use it to correctly identify type names and operation names. The glossary will be appended below this prompt.

---
[OPERATOR: Paste the C++ header content below this line. Optionally add a glossary section.]
